from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from contextlib import suppress
from dataclasses import dataclass, field

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings
from graphene_django.settings import graphene_settings
from graphql import ExecutionResult, parse
from graphql.language import OperationType
from graphql.language.ast import FieldNode, OperationDefinitionNode

from CypartaGraphqlSubscriptionsTools.models import *

from .utils import filter_requested_fields

logger = logging.getLogger(__name__)

# https://wundergraph.com/blog/quirks_of_graphql_subscriptions_sse_websockets_hasura_apollo_federation_supergraph#graphql-subscriptions-over-websockets:-subscription-transport-ws-vs-graphql-ws


def _field_node_response_key(sel: FieldNode) -> str:
    """GraphQL response key: alias if present, else field name."""
    return sel.alias.value if sel.alias else sel.name.value


def _first_root_field_key(defn: OperationDefinitionNode) -> str | None:
    if not defn.selection_set:
        return None
    for sel in defn.selection_set.selections:
        if isinstance(sel, FieldNode):
            return _field_node_response_key(sel)
    return None


def resolve_subscription_response_key(
    query: str, operation_name: str | None
) -> str | None:
    """
    Option B response key for the subscription (alias or field name).

    Expect one subscription operation per ``subscribe`` message. If the document
    contains several, ``operationName`` must match exactly one operation definition
    name or we log an error and return ``None``.
    """
    try:
        doc = parse(query)
    except Exception:
        logger.exception("subscription query parse failed")
        return None

    subs = [
        d
        for d in doc.definitions
        if isinstance(d, OperationDefinitionNode)
        and d.operation == OperationType.SUBSCRIPTION
    ]
    if not subs:
        return None

    if len(subs) == 1:
        defn = subs[0]
    else:
        if not operation_name:
            logger.error(
                "Multiple subscription operations in one document require operationName"
            )
            return None
        matching = [
            d for d in subs if d.name and d.name.value == operation_name
        ]
        if len(matching) != 1:
            logger.error(
                "operationName must identify exactly one subscription when multiple are present (name=%r)",
                operation_name,
            )
            return None
        defn = matching[0]

    key = _first_root_field_key(defn)
    if key is None:
        logger.error("Subscription operation has no field selection")
    return key


def subscription_root_field_from_query(query: str, fallback: str) -> str:
    """Best-effort first subscription root response key, or ``fallback`` if parse fails."""
    try:
        key = resolve_subscription_response_key(query, None)
        if key is not None:
            return key
        return fallback
    except Exception:
        return fallback


@dataclass(frozen=True)
class OutboundMessage:
    operation_id: str | None
    result: ExecutionResult


@dataclass
class OperationState:
    requested_fields: list | None
    groups: set[str] = field(default_factory=set)
    subscription_field_name: str | None = None


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
        self._ws_accepted = False
        self._connection_acknowledged = False
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
        else:
            await self.close(code=1002)
            return

        await self.accept(subprotocol=sec_websocket_protocol)
        self._ws_accepted = True

        self.ping_task = asyncio.ensure_future(self.send_ping())

    async def disconnect(self, close_code):
        if hasattr(self, "ping_task"):
            self.ping_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.ping_task

    async def send_ping(self):
        while True:
            try:
                await self.send_json({"type": self.ping_command})
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception(
                    "websocket ping send failed; stopping ping loop (disconnect in progress or transport closed)"
                )
                break
            try:
                await asyncio.sleep(self.ping_interval)
            except asyncio.CancelledError:
                break

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
    GraphQL subscriptions over Channels (production-oriented).

    - Bounded per-socket outbox queue + single sender task (no RxPY).
    - Subscriptions keyed by GraphQL transport ``id`` (``_ops`` / ``_group_ops``).
    - Live events use Option B: ``data = { "<responseKey>": serialized_value }``
      (response key = field alias or field name).
    """

    outbound_dropped_total: int = 0

    async def connect(self):
        maxsize = int(getattr(settings, "CYPARTA_WS_OUTBOX_MAXSIZE", 256) or 256)
        self._outbox: asyncio.Queue[OutboundMessage] = asyncio.Queue(maxsize=maxsize)
        self._sender_task: asyncio.Task | None = None
        self._group_ops: dict[str, set[str]] = defaultdict(set)
        self._ops: dict[str, OperationState] = {}
        self._active_operation_id: str | None = None
        self._active_subscription_field_name: str | None = None
        self._outbound_dropped = 0
        self.groups = {}
        self.requested_fields = None
        self.name = None
        await super().connect()
        if getattr(self, "_ws_accepted", False):
            self._sender_task = asyncio.create_task(self._outbox_sender())

    def _resolve_operation_id(self, explicit: str | None) -> str:
        op = explicit if explicit is not None else self._active_operation_id
        if not op:
            raise ValueError(
                "CypartaGraphqlSubscriptionsTools: operation_id is required "
                "(pass operation_id=... or rely on subscribe execution context)."
            )
        return str(op)

    async def _outbox_sender(self) -> None:
        while True:
            try:
                msg = await self._outbox.get()
            except asyncio.CancelledError:
                break
            try:
                await self._send_result(msg.operation_id, msg.result)
            except Exception:
                logger.exception("outbox_send_failed operation_id=%s", msg.operation_id)
            finally:
                self._outbox.task_done()

    def _enqueue(self, operation_id: str | None, result: ExecutionResult) -> None:
        try:
            self._outbox.put_nowait(
                OutboundMessage(operation_id=operation_id, result=result)
            )
        except asyncio.QueueFull:
            self._outbound_dropped += 1
            type(self).outbound_dropped_total += 1
            logger.warning(
                "subscription outbox full; dropped event operation_id=%s (per_connection=%s)",
                operation_id,
                self._outbound_dropped,
            )

    async def disconnect(self, close_code):
        await self._teardown_connection_resources()
        await super().disconnect(close_code)

    async def _teardown_connection_resources(self) -> None:
        if getattr(self, "_sender_task", None) is not None:
            self._sender_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._sender_task
            self._sender_task = None
        for group in list(self._group_ops.keys()):
            with suppress(Exception):
                await self.channel_layer.group_discard(group, self.channel_name)
        self._group_ops.clear()
        self._ops.clear()
        self.groups = {}

    async def detect_register_group_status(
        self,
        name_list,
        subscripe=True,
        requested_fields=None,
        operation_id=None,
    ):
        if subscripe:
            await self.register_group(
                name_list, subscripe, requested_fields, operation_id=operation_id
            )
        else:
            await self.un_register_group(
                name_list, subscripe, operation_id=operation_id
            )

    async def register_group(
        self,
        name_list,
        subscripe,
        requested_fields=None,
        operation_id=None,
    ):
        if not subscripe:
            await self.un_register_group(
                name_list, subscripe, operation_id=operation_id
            )
            return

        op_id = self._resolve_operation_id(operation_id)
        if op_id not in self._ops:
            self._ops[op_id] = OperationState(
                requested_fields=list(requested_fields) if requested_fields else None,
                groups=set(),
                subscription_field_name=self._active_subscription_field_name,
            )
        state = self._ops[op_id]
        if self._active_subscription_field_name:
            state.subscription_field_name = self._active_subscription_field_name
        if requested_fields:
            if state.requested_fields:
                state.requested_fields = list(
                    set(state.requested_fields) | set(requested_fields)
                )
            else:
                state.requested_fields = list(requested_fields)

        self.requested_fields = state.requested_fields

        for name in name_list:
            if name not in state.groups:
                state.groups.add(name)
                await self.channel_layer.group_add(name, self.channel_name)
            self._group_ops[name].add(op_id)

        self.name = name_list[-1] if name_list else None
        self.groups = {g: True for g in state.groups}

        self._enqueue(
            op_id,
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

    async def un_register_group(
        self, name_list, subscripe, operation_id=None
    ):
        op_id = self._resolve_operation_id(operation_id)
        state = self._ops.get(op_id)
        for name in name_list:
            if state and name in state.groups:
                state.groups.discard(name)
            if name in self._group_ops:
                self._group_ops[name].discard(op_id)
                if not self._group_ops[name]:
                    del self._group_ops[name]
                    await self.channel_layer.group_discard(name, self.channel_name)

        self._enqueue(
            op_id,
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

    async def _complete_operation(self, operation_id: str | None) -> None:
        if operation_id is None:
            return
        op_id = str(operation_id)
        state = self._ops.get(op_id)
        if not state:
            return
        for group in list(state.groups):
            if group in self._group_ops:
                self._group_ops[group].discard(op_id)
                if not self._group_ops[group]:
                    del self._group_ops[group]
                    await self.channel_layer.group_discard(group, self.channel_name)
        del self._ops[op_id]
        await self.send_json({"type": "complete", "id": op_id})

    async def execute_subscription(
        self,
        query: str,
        operation_name,
        variables,
        context,
        operation_id: str | None,
        subscription_field_name: str,
    ):
        op_id = self._resolve_operation_id(operation_id)
        self._active_operation_id = op_id
        self._active_subscription_field_name = subscription_field_name
        try:
            schema = graphene_settings.SCHEMA
            result = await sync_to_async(schema.execute)(
                query,
                operation_name=operation_name,
                variables=variables,
                context=context,
                root=self,
            )
            state = self._ops.get(op_id)
            if state and state.groups:
                return
            self._enqueue(op_id, result)
        finally:
            self._active_operation_id = None
            self._active_subscription_field_name = None

    async def receive_json(self, request):
        self.name = None
        message_type = request.get("type")

        if message_type == "connection_init":
            await self.send_json({"type": "connection_ack"})
            self._connection_acknowledged = True

        elif message_type == "subscribe":
            if not getattr(self, "_connection_acknowledged", False):
                await self.close(code=4401)
                return
            operation_id = request.get("id")
            if operation_id is None:
                logger.warning("subscribe message missing id")
                return
            operation_id = str(operation_id)
            payload = request["payload"]
            variables = payload.get("variables")
            operation_name = payload.get("operationName")
            context = AttrDict(self.scope)
            query = payload["query"]

            field_key = resolve_subscription_response_key(query, operation_name)
            if field_key is None:
                logger.error(
                    "subscribe rejected: could not resolve subscription response key"
                )
                return

            await self.execute_subscription(
                query,
                operation_name,
                variables,
                context,
                operation_id,
                field_key,
            )

        elif message_type == "complete":
            if request.get("id") is not None:
                await self._complete_operation(request.get("id"))

        else:
            logger.warning(
                "unknown or unsupported graphql-ws message type: %r",
                message_type,
            )

    def _shallow_copy_event_value(self, raw):
        if isinstance(raw, dict):
            out = dict(raw)
            fld = raw.get("fields")
            if isinstance(fld, dict):
                out["fields"] = dict(fld)
            return out
        return raw

    async def subscription_triggered(self, message):
        group = message["group"]
        op_ids = self._group_ops.get(group)
        if not op_ids:
            return
        for op_id in list(op_ids):
            state = self._ops.get(op_id)
            if not state:
                continue
            raw = self._shallow_copy_event_value(message["value"])
            serialized_value = filter_requested_fields(raw, state.requested_fields)
            key = state.subscription_field_name or "subscription"
            self._enqueue(
                op_id,
                ExecutionResult(
                    data={key: serialized_value},
                    errors=None,
                    extensions=None,
                ),
            )
