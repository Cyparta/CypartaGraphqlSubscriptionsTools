from __future__ import annotations

import asyncio
from collections import defaultdict
from contextlib import suppress
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from graphql import ExecutionResult

from CypartaGraphqlSubscriptionsTools.consumers import (
    CypartaGraphqlSubscriptionsConsumer,
    DetectWebSocketType,
    OperationState,
    OutboundMessage,
    resolve_subscription_response_key,
    subscription_root_field_from_query,
)


def test_resolve_subscription_response_key_simple():
    q = """
    subscription SubName {
      myModelUpdated(id: "1", subscripe: true) {
        id
        name
      }
    }
    """
    assert resolve_subscription_response_key(q, None) == "myModelUpdated"


def test_alias_response_key_for_option_b():
    """Option B WebSocket key is the GraphQL response key (alias), not the field name."""
    q = """subscription { ev: myModelUpdated { id } }"""
    assert resolve_subscription_response_key(q, None) == "ev"


def test_multiple_subscriptions_without_operation_name_returns_none():
    q = """
    subscription A { x { id } }
    subscription B { y { id } }
    """
    assert resolve_subscription_response_key(q, None) is None


def test_multiple_subscriptions_with_operation_name_selects_field():
    q = """
    subscription A { x { id } }
    subscription B { y { id } }
    """
    assert resolve_subscription_response_key(q, "B") == "y"


def test_subscription_root_field_from_query_fallback():
    assert subscription_root_field_from_query("not graphql", "fallback") == "fallback"


def _minimal_consumer(scope):
    """Channels consumers get ``scope`` from ``__call__``; tests assign it manually."""
    c = CypartaGraphqlSubscriptionsConsumer()
    c.scope = scope
    c.base_send = AsyncMock()
    c.channel_layer = MagicMock()
    c.channel_name = "test-channel"
    return c


@pytest.mark.asyncio
async def test_unsupported_websocket_protocol_no_ping():
    scope = {
        "type": "websocket",
        "path": "/ws/graphql/",
        "headers": [(b"sec-websocket-protocol", b"invalid-protocol")],
    }
    consumer = _minimal_consumer(scope)
    with patch.object(consumer, "close", new_callable=AsyncMock) as close_mock:
        await consumer.connect()
    close_mock.assert_awaited_once()
    assert not getattr(consumer, "_ws_accepted", True)
    assert not hasattr(consumer, "ping_task")


@pytest.mark.asyncio
async def test_subscribe_before_connection_init_rejected_with_4401():
    scope = {
        "type": "websocket",
        "path": "/ws/graphql/",
        "headers": [(b"sec-websocket-protocol", b"graphql-transport-ws")],
    }
    consumer = _minimal_consumer(scope)
    consumer.close = AsyncMock()
    consumer.send_json = AsyncMock()
    await consumer.connect()
    assert consumer._connection_acknowledged is False
    await consumer.receive_json(
        {
            "type": "subscribe",
            "id": "1",
            "payload": {"query": "subscription { myF { id } }"},
        }
    )
    consumer.close.assert_awaited()
    assert consumer.close.await_args.kwargs.get("code") == 4401


@pytest.mark.asyncio
async def test_complete_without_connection_init_allowed_when_id_present():
    scope = {
        "type": "websocket",
        "path": "/ws/graphql/",
        "headers": [(b"sec-websocket-protocol", b"graphql-transport-ws")],
    }
    consumer = _minimal_consumer(scope)
    consumer.send_json = AsyncMock()
    await consumer.connect()
    assert consumer._connection_acknowledged is False
    with patch.object(consumer, "_complete_operation", new_callable=AsyncMock) as complete_mock:
        await consumer.receive_json({"type": "complete", "id": "99"})
    complete_mock.assert_awaited_once_with("99")


@pytest.mark.asyncio
async def test_unknown_message_type_logs_warning():
    scope = {
        "type": "websocket",
        "path": "/ws/graphql/",
        "headers": [(b"sec-websocket-protocol", b"graphql-transport-ws")],
    }
    consumer = _minimal_consumer(scope)
    consumer.send_json = AsyncMock()
    await consumer.connect()
    with patch("CypartaGraphqlSubscriptionsTools.consumers.logger") as log_mock:
        await consumer.receive_json({"type": "not_a_real_type"})
        log_mock.warning.assert_called()


@pytest.mark.asyncio
async def test_ping_task_exits_when_send_json_fails():
    c = DetectWebSocketType()
    c.scope = {"type": "websocket", "path": "/", "headers": []}
    c.base_send = AsyncMock()
    c.ping_command = "ping"

    async def broken_send_json(_data):
        raise OSError("simulated transport failure")

    c.send_json = broken_send_json
    with patch("asyncio.sleep", new_callable=AsyncMock):
        task = asyncio.create_task(c.send_ping())
        await asyncio.wait_for(task, timeout=2.0)
    assert task.done()
    assert not task.cancelled()


@pytest.mark.asyncio
async def test_disconnect_cancels_ping_no_websocket_close_json():
    scope = {
        "type": "websocket",
        "path": "/ws/graphql/",
        "headers": [(b"sec-websocket-protocol", b"graphql-transport-ws")],
    }
    consumer = _minimal_consumer(scope)
    consumer.channel_layer.group_discard = AsyncMock()
    sends = []

    async def capture_send_json(data):
        sends.append(data)

    consumer.send_json = capture_send_json
    consumer.close = AsyncMock()
    await consumer.connect()
    assert consumer._ws_accepted is True
    assert hasattr(consumer, "ping_task")
    consumer.ping_task.cancel()
    with suppress(asyncio.CancelledError):
        await consumer.ping_task
    consumer.ping_task = asyncio.create_task(asyncio.sleep(999))
    await consumer.disconnect(1000)
    assert not any(
        isinstance(x, dict) and x.get("type") == "websocket.close" for x in sends
    )


@pytest.mark.asyncio
async def test_queue_overflow_bounded():
    c = object.__new__(CypartaGraphqlSubscriptionsConsumer)
    CypartaGraphqlSubscriptionsConsumer.outbound_dropped_total = 0
    c._outbound_dropped = 0
    c._outbox = asyncio.Queue(maxsize=2)
    for i in range(2):
        c._outbox.put_nowait(
            OutboundMessage(
                "1",
                ExecutionResult(data={"s": {"i": i}}, errors=None, extensions=None),
            )
        )
    CypartaGraphqlSubscriptionsConsumer._enqueue(
        c,
        "1",
        ExecutionResult(data={"s": {"i": 2}}, errors=None, extensions=None),
    )
    assert c._outbox.qsize() == 2
    assert c._outbound_dropped == 1
    assert CypartaGraphqlSubscriptionsConsumer.outbound_dropped_total == 1


@pytest.mark.asyncio
async def test_one_operation_subscribes_to_one_group_option_b_shape():
    c = object.__new__(CypartaGraphqlSubscriptionsConsumer)
    enqueued: list[tuple[str, ExecutionResult]] = []

    def capture_enqueue(oid, res):
        enqueued.append((oid, res))

    c._enqueue = capture_enqueue
    c._group_ops = defaultdict(set, {"G1": {"op1"}})
    c._ops = {
        "op1": OperationState(
            requested_fields=None,
            groups={"G1"},
            subscription_field_name="myModelUpdated",
        )
    }
    await c.subscription_triggered(
        {"group": "G1", "value": {"pk": 10, "fields": {"id": 10, "name": "Test"}}}
    )
    assert len(enqueued) == 1
    oid, res = enqueued[0]
    assert oid == "op1"
    assert res.data == {
        "myModelUpdated": {"pk": 10, "fields": {"id": 10, "name": "Test"}}
    }
    assert res.extensions is None and res.errors is None


@pytest.mark.asyncio
async def test_two_operations_same_group_two_payloads():
    c = object.__new__(CypartaGraphqlSubscriptionsConsumer)
    enqueued: list[str] = []

    def capture_enqueue(oid, res):
        enqueued.append(oid)

    c._enqueue = capture_enqueue
    c._group_ops = defaultdict(set, {"G": {"a", "b"}})
    c._ops = {
        "a": OperationState(None, {"G"}, "fieldA"),
        "b": OperationState(None, {"G"}, "fieldB"),
    }
    await c.subscription_triggered(
        {"group": "G", "value": {"pk": 1, "fields": {"id": 1}}}
    )
    assert set(enqueued) == {"a", "b"}


@pytest.mark.asyncio
async def test_complete_removes_one_operation():
    c = object.__new__(CypartaGraphqlSubscriptionsConsumer)
    c.channel_layer = MagicMock()
    c.channel_layer.group_discard = AsyncMock()
    c.channel_name = "ch"
    c._group_ops = defaultdict(set, {"G": {"1", "2"}})
    c._ops = {
        "1": OperationState(None, {"G"}, "f1"),
        "2": OperationState(None, {"G"}, "f2"),
    }
    c.send_json = AsyncMock()
    await c._complete_operation("1")
    assert "1" not in c._ops
    assert "2" in c._ops
    assert c._group_ops["G"] == {"2"}
    c.send_json.assert_awaited_once_with({"type": "complete", "id": "1"})


@pytest.mark.asyncio
async def test_one_operation_two_groups_both_routed():
    c = object.__new__(CypartaGraphqlSubscriptionsConsumer)
    hits = []

    def capture_enqueue(oid, res):
        hits.append(res.data)

    c._enqueue = capture_enqueue
    c._group_ops = defaultdict(set, {"G1": {"op1"}, "G2": {"op1"}})
    c._ops = {
        "op1": OperationState(None, {"G1", "G2"}, "rootField"),
    }
    await c.subscription_triggered(
        {"group": "G1", "value": {"pk": 1, "fields": {"id": 1}}}
    )
    await c.subscription_triggered(
        {"group": "G2", "value": {"pk": 2, "fields": {"id": 2}}}
    )
    assert len(hits) == 2
    assert hits[0] == {"rootField": {"pk": 1, "fields": {"id": 1}}}
    assert hits[1] == {"rootField": {"pk": 2, "fields": {"id": 2}}}
