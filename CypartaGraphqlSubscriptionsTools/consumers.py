from __future__ import annotations

import asyncio
import copy
import logging
import re

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from graphene_django.settings import graphene_settings
from graphql import ExecutionResult
from reactivex.subject import Subject

from CypartaGraphqlSubscriptionsTools.models import *

from .utils import filter_requested_fields

logger = logging.getLogger(__name__)

# https://wundergraph.com/blog/quirks_of_graphql_subscriptions_sse_websockets_hasura_apollo_federation_supergraph#graphql-subscriptions-over-websockets:-subscription-transport-ws-vs-graphql-ws


class AttrDict:
    def __init__(self, data):
        self.data = data or {}

    def __getattr__(self, item):
        return self.get(item)

    def get(self, item):
        return self.data.get(item)


class DetectWebSocketType(AsyncJsonWebsocketConsumer):
    ping_interval = 10

    async def connect(self):
        headers_dict = dict(self.scope.get("headers", []))
        sec_websocket_protocol = headers_dict.get(
            b"sec-websocket-protocol", b""
        ).decode("utf-8")

        if sec_websocket_protocol == "graphql-transport-ws":
            self.ping_command = "ping"
            self.start_command = "subscribe"
            self.result_command = "next"
            self.end_command = "complete"
        elif sec_websocket_protocol == "graphql-ws":
            self.ping_command = "ka"
            self.start_command = "start"
            self.result_command = "data"
            self.end_command = "stop"

        await self.accept(subprotocol=sec_websocket_protocol)

        self.ping_task = asyncio.ensure_future(self.send_ping())

    async def disconnect(self, close_code):
        await self.send_json({"type": "websocket.close", "code": 1000})
        for group in getattr(self, "groups", {}):
            await self.channel_layer.group_discard(group, self.channel_name)
        if hasattr(self, "ping_task"):
            self.ping_task.cancel()

    async def send_ping(self):
        while True:
            await self.send_json({"type": self.ping_command})
            await asyncio.sleep(self.ping_interval)

    async def _send_result(self, id, result: ExecutionResult):
        if not isinstance(result, ExecutionResult):
            raise TypeError(
                "CypartaGraphqlSubscriptionsTools: payload must be graphql.ExecutionResult; "
                f"got {type(result)!r}"
            )
        errors = result.errors
        formatted_errors = (
            [error.formatted for error in errors] if errors else None
        )
        payload: dict = {
            "data": result.data,
            "errors": formatted_errors,
        }
        if result.extensions:
            payload["extensions"] = result.extensions
        await self.send_json(
            {
                "id": id,
                "type": self.result_command,
                "payload": payload,
            }
        )


class CypartaGraphqlSubscriptionsConsumer(DetectWebSocketType):
    """
    GraphQL subscriptions over Channels.

    **v2 changes**
    - ``groups`` is per WebSocket connection (set in :meth:`connect`), not a class attribute.
    - Channel events are mapped with :meth:`adapt_channel_event` and only
      ``graphql.ExecutionResult`` is sent (no raw ``AttrDict`` as ``data``).
    - Registration ack uses ``extensions.cyparta`` (``data`` is ``null``).

    Optional Django settings:

    - ``CYPARTA_GRAPHQL_SUBSCRIPTION_ADAPTER``: dotted path to async callable
      ``(consumer, operation_id, group, value, requested_fields) -> ExecutionResult | None``.
    - ``CYPARTA_LEGACY_SUBSCRIPTION_DATA``: if ``True``, default adapter puts the
      serialized dict on ``data`` (legacy wire shape; not valid GraphQL field data).
    """

    async def connect(self):
        self.groups = {}
        self.requested_fields = None
        await super().connect()

    async def adapt_channel_event(self, operation_id, group, value, requested_fields):
        """Resolve channel payload → ``ExecutionResult``. Override or set ``CYPARTA_GRAPHQL_SUBSCRIPTION_ADAPTER``."""
        from django.conf import settings
        from django.utils.module_loading import import_string

        path = getattr(settings, "CYPARTA_GRAPHQL_SUBSCRIPTION_ADAPTER", None) or ""
        path = str(path).strip()
        if path:
            return await import_string(path)(
                self, operation_id, group, value, requested_fields
            )
        return await self.default_adapt_channel_event(
            operation_id, group, value, requested_fields
        )

    async def default_adapt_channel_event(
        self, operation_id, group, value, requested_fields
    ):
        from django.conf import settings

        if getattr(settings, "CYPARTA_LEGACY_SUBSCRIPTION_DATA", False):
            return ExecutionResult(data=value, errors=None, extensions=None)
        return ExecutionResult(
            data=None,
            errors=None,
            extensions={"cypartaSubscriptionEvent": value},
        )

    async def detect_register_group_status(
        self, name_list, subscripe=True, requested_fields=None
    ):
        if subscripe:
            await self.register_group(name_list, subscripe, requested_fields)
        else:
            await self.un_register_group(name_list, subscripe)

    async def register_group(self, name_list, subscripe, requested_fields=None):
        self.requested_fields = requested_fields
        stream = Subject()
        for name in name_list:
            self.name = name
            if self.name not in self.groups:
                self.groups[self.name] = stream
                await self.channel_layer.group_add(self.name, self.channel_name)

        await self._send_result(
            self.id,
            ExecutionResult(
                data=None,
                errors=None,
                extensions={
                    "cyparta": {
                        "registeredGroups": list(name_list),
                        "subscripe": subscripe,
                        "action": "register",
                    }
                },
            ),
        )

    async def un_register_group(self, name_list, subscripe):
        for name in name_list:
            if name in self.groups:
                self.name = None
                await self.channel_layer.group_discard(name, self.channel_name)

        await self._send_result(
            self.id,
            ExecutionResult(
                data=None,
                errors=None,
                extensions={
                    "cyparta": {
                        "registeredGroups": list(name_list),
                        "subscripe": subscripe,
                        "action": "unregister",
                    }
                },
            ),
        )

    async def extract_subscriptions(self, payload):
        query = payload["query"]
        subscriptions_list = re.findall(
            r"subscription (\w+) {([^}]+}\s*)}", query
        )
        return subscriptions_list

    async def execute_subscription(
        self, subscription, operation_name, variables, context, id
    ):
        schema = graphene_settings.SCHEMA
        result = await sync_to_async(schema.execute)(
            subscription,
            operation_name=operation_name,
            variables=variables,
            context=context,
            root=self,
        )
        if self.name is not None:
            self.groups[self.name].subscribe(
                lambda data: asyncio.ensure_future(self._send_result(id, data))
            )
        else:
            await self._send_result(id, result)

    async def process_subscriptions(
        self, subscriptions_list, variables, context, id
    ):
        for operation_name, subscription_body in subscriptions_list:
            subscription = (
                f"subscription {operation_name} {{{subscription_body.strip()}}}"
            )
            await self.execute_subscription(
                subscription,
                operation_name=operation_name,
                variables=variables,
                context=context,
                id=id,
            )

    async def receive_json(self, request):
        self.id = request.get("id")
        self.name = None
        if request["type"] == "connection_init":
            await self.send_json({"type": "connection_ack"})
        if request["type"] == "subscribe":
            payload = request["payload"]
            variables = payload.get("variables")
            operation_name = payload.get("operationName")
            query = payload["query"]
            context = AttrDict(self.scope)

            subscriptions_list = await self.extract_subscriptions(payload)
            if len(subscriptions_list) > 0:
                await self.process_subscriptions(
                    subscriptions_list, variables, context, self.id
                )
            else:
                await self.execute_subscription(
                    query, operation_name, variables, context, self.id
                )

        if request["type"] == "complete":
            pass

    async def subscription_triggered(self, message):
        group = message["group"]
        if group not in self.groups:
            return
        stream = self.groups[group]
        raw = copy.deepcopy(message["value"])
        serialized_value = filter_requested_fields(raw, self.requested_fields)
        try:
            exec_result = await self.adapt_channel_event(
                self.id, group, serialized_value, self.requested_fields
            )
        except Exception:
            logger.exception(
                "adapt_channel_event failed group=%s operation_id=%s",
                group,
                self.id,
            )
            return
        if exec_result is not None:
            stream.on_next(exec_result)
