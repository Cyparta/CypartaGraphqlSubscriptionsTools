from channels.generic.websocket import AsyncJsonWebsocketConsumer
from CypartaGraphqlSubscriptionsTools.serialize import serialize_value
#from CypartaGraphqlSubscriptionsTools.schema import schema  # Import your GraphQL schema
from reactivex.subject import Subject
import asyncio
import re
from asgiref.sync import sync_to_async
from CypartaGraphqlSubscriptionsTools.models import *
from graphene_django.settings import graphene_settings
from .utils import filter_requested_fields
# use full link https://wundergraph.com/blog/quirks_of_graphql_subscriptions_sse_websockets_hasura_apollo_federation_supergraph#graphql-subscriptions-over-websockets:-subscription-transport-ws-vs-graphql-ws
# #if we will use Sec-Websocket-Protocol: graphql-ws

class AttrDict:
    def __init__(self, data):
        # Initialize AttrDict with data
        self.data = data or {}

    def __getattr__(self, item):
        # Get attribute by name
        return self.get(item)

    def get(self, item):
        # Get item from data
        return self.data.get(item)

class DetectWebSocketType(AsyncJsonWebsocketConsumer):
    # Constants for different WebSocket implementations
    ping_interval = 10  # Set your desired ping interval in seconds
    
    async def connect(self):
        # Determine WebSocket protocol based on Sec-WebSocket-Protocol header
        headers_dict = dict(self.scope.get("headers", []))
        sec_websocket_protocol = headers_dict.get(b"sec-websocket-protocol", b"").decode("utf-8")
        
        if sec_websocket_protocol == 'graphql-transport-ws':
            self.ping_command = 'ping'
            self.start_command = 'subscribe'
            self.result_command = 'next'
            self.end_command = 'complete'
        elif sec_websocket_protocol == 'graphql-ws':
            self.ping_command = 'ka'
            self.start_command = 'start'
            self.result_command = 'data'
            self.end_command = 'stop'

        await self.accept(subprotocol=sec_websocket_protocol)

        # Set up ping task to keep the connection alive
        self.ping_task = asyncio.ensure_future(self.send_ping())

    async def disconnect(self, close_code):
        # Disconnect WebSocket and discard groups
        await self.send_json({"type": "websocket.close", "code": 1000})
        for group in self.groups:
            await self.channel_layer.group_discard(group, self.channel_name)
        if hasattr(self, 'ping_task'):
            self.ping_task.cancel()

    async def send_ping(self):
        # Periodically send ping messages to keep the connection alive
        while True:
            await self.send_json({'type': self.ping_command})
            await asyncio.sleep(self.ping_interval)

    async def _send_result(self, id, result):
        # Send subscription results back to the client
        await self.send_json(
            {
                "id": id,
                "type": self.result_command,
                "payload": {
                    "data": result.data,
                },
            }
        )

class CypartaGraphqlSubscriptionsConsumer(DetectWebSocketType):
    # Dictionary to store WebSocket groups
    groups = {}

    async def detect_register_group_status(self, name_list, subscripe=True, requested_fields=None):
        # Detect and register/unregister WebSocket groups
        if subscripe:
            await self.register_group(name_list, subscripe, requested_fields)
        else:
            await self.un_register_group(name_list, subscripe)

    async def register_group(self, name_list, subscripe, requested_fields=None):
        # Register WebSocket groups
        self.requested_fields = requested_fields
        stream = Subject()
        for name in name_list:
            self.name = name
            if self.name not in self.groups:
                self.groups[self.name] = stream
                await self.channel_layer.group_add(self.name, self.channel_name)

        data = AttrDict({'group-subscription': name_list, 'status': subscripe})
        await self._send_result(self.id, data)

    async def un_register_group(self, name_list, subscripe):
        # Unregister WebSocket groups
        for name in name_list:
            if name in self.groups:
                self.name = None
                await self.channel_layer.group_discard(name, self.channel_name)

        data = AttrDict({'group-subscription': name_list, 'status': subscripe})
        await self._send_result(self.id, data)

    async def extract_subscriptions(self, payload):
        # Extract subscriptions from the GraphQL query
        query = payload["query"]
        subscriptions_list = re.findall(r'subscription (\w+) {([^}]+}\s*)}', query)
        return subscriptions_list

    async def execute_subscription(self, subscription, operation_name, variables, context, id):
        # Execute the GraphQL subscription and send results
        schema = graphene_settings.SCHEMA
        result = await sync_to_async(schema.execute)(
            subscription,
            operation_name=operation_name,
            variables=variables,
            context=context,
            root=self,
        )
        if self.name is not None:
            self.groups[self.name].subscribe(lambda data: asyncio.ensure_future(self._send_result(id, data)))
        else:
            await self._send_result(id, result)

    async def process_subscriptions(self, subscriptions_list, variables, context, id):
        # Process multiple subscriptions
        for operation_name, subscription_body in subscriptions_list:
            subscription = f'subscription {operation_name} {{{subscription_body.strip()}}}'
            await self.execute_subscription(
                subscription,
                operation_name=operation_name,
                variables=variables,
                context=context,
                id=id
            )

    async def receive_json(self, request):
        # Receive JSON messages and handle GraphQL subscriptions
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
                await self.process_subscriptions(subscriptions_list, variables, context, self.id)
            else:
                await self.execute_subscription(query, operation_name, variables, context, self.id)

        if request["type"] == "complete":
            pass

    async def subscription_triggered(self, message):
        # Handle triggered subscriptions and send results to clients
        group = message['group']
        if group in self.groups:
            stream = self.groups[group]
            #serialized_value = await serialize_value(message['value'], self.requested_fields, group)
            serialized_filter_value=filter_requested_fields(message['value'],self.requested_fields)
            stream.on_next(AttrDict(serialized_filter_value))
