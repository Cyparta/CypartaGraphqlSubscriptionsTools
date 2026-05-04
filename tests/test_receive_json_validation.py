"""receive_json shape validation and send_operation_error behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from CypartaGraphqlSubscriptionsTools.consumers import CypartaGraphqlSubscriptionsConsumer


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
