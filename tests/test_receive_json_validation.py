"""receive_json shape validation and send_operation_error behavior."""

from __future__ import annotations

from collections import defaultdict
from unittest.mock import AsyncMock, patch

import pytest

from CypartaGraphqlSubscriptionsTools.consumers import (
    CypartaGraphqlSubscriptionsConsumer,
    OperationState,
)


def _transport_ws_consumer():
    scope = {
        "type": "websocket",
        "path": "/ws/graphql/",
        "headers": [(b"sec-websocket-protocol", b"graphql-transport-ws")],
    }
    c = CypartaGraphqlSubscriptionsConsumer()
    c.scope = scope
    c.base_send = AsyncMock()
    c.channel_layer = AsyncMock()
    c.channel_name = "ch-test"
    return c


@pytest.mark.asyncio
async def test_receive_json_non_dict_does_not_crash():
    c = _transport_ws_consumer()
    c.send_json = AsyncMock()
    await c.connect()
    await c.receive_json(None)
    await c.receive_json([1, 2, 3])


@pytest.mark.asyncio
async def test_subscribe_missing_payload_sends_error_transport_ws():
    c = _transport_ws_consumer()
    c.send_json = AsyncMock()
    await c.connect()
    await c.receive_json({"type": "connection_init"})
    await c.receive_json({"type": "subscribe", "id": "op-missing-payload"})

    err_calls = [
        a[0][0]
        for a in c.send_json.await_args_list
        if isinstance(a[0][0], dict) and a[0][0].get("type") == "error"
    ]
    assert err_calls
    assert err_calls[-1]["id"] == "op-missing-payload"
    assert isinstance(err_calls[-1]["payload"], list)
    assert err_calls[-1]["payload"][0]["message"]


@pytest.mark.asyncio
async def test_subscribe_payload_not_dict_sends_error():
    c = _transport_ws_consumer()
    c.send_json = AsyncMock()
    await c.connect()
    await c.receive_json({"type": "connection_init"})
    await c.receive_json({"type": "subscribe", "id": "1", "payload": "not-a-dict"})

    last = c.send_json.await_args_list[-1][0][0]
    assert last["type"] == "error"
    assert last["id"] == "1"


@pytest.mark.asyncio
async def test_subscribe_missing_query_sends_error():
    c = _transport_ws_consumer()
    c.send_json = AsyncMock()
    await c.connect()
    await c.receive_json({"type": "connection_init"})
    await c.receive_json({"type": "subscribe", "id": "2", "payload": {"variables": {}}})

    last = c.send_json.await_args_list[-1][0][0]
    assert last["type"] == "error"
    assert last["id"] == "2"


@pytest.mark.asyncio
async def test_subscribe_query_not_string_sends_error():
    c = _transport_ws_consumer()
    c.send_json = AsyncMock()
    await c.connect()
    await c.receive_json({"type": "connection_init"})
    await c.receive_json(
        {"type": "subscribe", "id": "3", "payload": {"query": 123}}
    )

    last = c.send_json.await_args_list[-1][0][0]
    assert last["type"] == "error"


@pytest.mark.asyncio
async def test_subscribe_variables_invalid_type_sends_error():
    c = _transport_ws_consumer()
    c.send_json = AsyncMock()
    await c.connect()
    await c.receive_json({"type": "connection_init"})
    await c.receive_json(
        {
            "type": "subscribe",
            "id": "4",
            "payload": {"query": "subscription { a { id } }", "variables": [1, 2]},
        }
    )

    last = c.send_json.await_args_list[-1][0][0]
    assert last["type"] == "error"


@pytest.mark.asyncio
async def test_subscribe_operation_name_invalid_type_sends_error():
    c = _transport_ws_consumer()
    c.send_json = AsyncMock()
    await c.connect()
    await c.receive_json({"type": "connection_init"})
    await c.receive_json(
        {
            "type": "subscribe",
            "id": "5",
            "payload": {
                "query": "subscription S { a { id } }",
                "operationName": 99,
            },
        }
    )

    last = c.send_json.await_args_list[-1][0][0]
    assert last["type"] == "error"


@pytest.mark.asyncio
async def test_subscribe_valid_reaches_execute_subscription():
    c = _transport_ws_consumer()
    c.send_json = AsyncMock()
    await c.connect()
    await c.receive_json({"type": "connection_init"})
    with patch.object(
        c, "execute_subscription", new_callable=AsyncMock
    ) as exec_mock:
        await c.receive_json(
            {
                "type": "subscribe",
                "id": "6",
                "payload": {
                    "query": "subscription { myF { id } }",
                    "variables": {"x": 1},
                    "operationName": None,
                },
            }
        )
    exec_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_legacy_graphql_ws_error_payload_is_object_not_list():
    scope = {
        "type": "websocket",
        "path": "/ws/graphql/",
        "headers": [(b"sec-websocket-protocol", b"graphql-ws")],
    }
    c = CypartaGraphqlSubscriptionsConsumer()
    c.scope = scope
    c.base_send = AsyncMock()
    c.channel_layer = AsyncMock()
    c.channel_name = "ch-legacy"
    c.send_json = AsyncMock()
    await c.connect()
    assert c.start_command == "start"
    await c.receive_json({"type": "connection_init"})
    await c.receive_json({"type": "start", "id": "L1", "payload": None})

    err = next(
        a[0][0]
        for a in c.send_json.await_args_list
        if isinstance(a[0][0], dict) and a[0][0].get("type") == "error"
    )
    assert err["id"] == "L1"
    assert isinstance(err["payload"], dict)
    assert "message" in err["payload"]


@pytest.mark.asyncio
async def test_duplicate_connection_init_closes_with_4429():
    c = _transport_ws_consumer()
    c.send_json = AsyncMock()
    c.close = AsyncMock()
    await c.connect()
    await c.receive_json({"type": "connection_init"})
    await c.receive_json({"type": "connection_init"})
    c.close.assert_awaited()
    assert c.close.await_args.kwargs.get("code") == 4429


@pytest.mark.asyncio
async def test_ping_replies_pong_transport_ws():
    c = _transport_ws_consumer()
    c.send_json = AsyncMock()
    await c.connect()
    await c.receive_json({"type": "connection_init"})
    await c.receive_json({"type": "ping"})
    pong = next(
        a[0][0]
        for a in c.send_json.await_args_list
        if isinstance(a[0][0], dict) and a[0][0].get("type") == "pong"
    )
    assert pong == {"type": "pong"}


@pytest.mark.asyncio
async def test_pong_is_noop():
    c = _transport_ws_consumer()
    c.send_json = AsyncMock()
    await c.connect()
    n_before = len(c.send_json.await_args_list)
    await c.receive_json({"type": "pong"})
    assert len(c.send_json.await_args_list) == n_before


@pytest.mark.asyncio
async def test_connection_terminate_closes_socket():
    c = _transport_ws_consumer()
    c.send_json = AsyncMock()
    c.close = AsyncMock()
    await c.connect()
    await c.receive_json({"type": "connection_terminate"})
    c.close.assert_awaited()
    assert c.close.await_args.kwargs.get("code") == 1000


@pytest.mark.asyncio
async def test_legacy_complete_operation_outbound_type_not_stop():
    scope = {
        "type": "websocket",
        "path": "/ws/",
        "headers": [(b"sec-websocket-protocol", b"graphql-ws")],
    }
    c = CypartaGraphqlSubscriptionsConsumer()
    c.scope = scope
    c.base_send = AsyncMock()
    c.channel_layer = AsyncMock()
    c.channel_name = "ch-legacy"
    await c.connect()
    assert c.end_command == "stop"
    c._group_ops = defaultdict(set, {"G": {"1"}})
    c._ops = {"1": OperationState(None, {"G"}, "f")}
    c.send_json = AsyncMock()
    await c._complete_operation("1")
    c.send_json.assert_awaited_once_with({"type": "complete", "id": "1"})
