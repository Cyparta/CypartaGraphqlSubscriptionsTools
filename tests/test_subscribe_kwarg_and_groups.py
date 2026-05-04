"""Tests for ``subscribe`` kwarg, extensions, and group name validation in consumers."""

from __future__ import annotations

from collections import defaultdict
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from django.test import override_settings

from CypartaGraphqlSubscriptionsTools.consumers import CypartaGraphqlSubscriptionsConsumer


def _bare_consumer(scope):
    c = object.__new__(CypartaGraphqlSubscriptionsConsumer)
    c.scope = scope
    c.channel_layer = MagicMock()
    c.channel_layer.group_add = AsyncMock()
    c.channel_layer.group_discard = AsyncMock()
    c.channel_name = "test-ch"
    c._group_ops = defaultdict(set)
    c._ops = {}
    c._active_subscription_field_name = "subField"
    c._active_subscribe_variables = {}
    return c


@pytest.mark.asyncio
@override_settings(CYPARTA_WS_REQUIRE_AUTH=True, CYPARTA_WS_STRICT_GROUP_NAMES=True)
async def test_register_invalid_group_name_strict_no_group_add():
    user = SimpleNamespace(is_anonymous=False, pk=1)
    c = _bare_consumer({"type": "websocket", "user": user})
    c._active_operation_id = "op1"
    enqueued = []
    c._enqueue = lambda oid, res: enqueued.append(res)

    await c.register_group(["bad group"], True, None, operation_id="op1")

    c.channel_layer.group_add.assert_not_awaited()
    assert any(r.errors for r in enqueued if r.errors)


@pytest.mark.asyncio
@override_settings(CYPARTA_WS_REQUIRE_AUTH=True, CYPARTA_WS_STRICT_GROUP_NAMES=False)
async def test_register_non_strict_normalizes_group_name():
    user = SimpleNamespace(is_anonymous=False, pk=1)
    c = _bare_consumer({"type": "websocket", "user": user})
    c._active_operation_id = "op1"
    c._enqueue = MagicMock()

    await c.register_group(["ok group"], True, None, operation_id="op1")

    c.channel_layer.group_add.assert_awaited_once_with("ok_group", "test-ch")
    assert "op1" in c._group_ops["ok_group"]


@pytest.mark.asyncio
@override_settings(CYPARTA_WS_REQUIRE_AUTH=True)
async def test_extensions_include_subscribe_and_deprecation_notes():
    user = SimpleNamespace(is_anonymous=False, pk=1)
    c = _bare_consumer({"type": "websocket", "user": user})
    c._active_operation_id = "op1"
    captured = []

    def cap(oid, res):
        captured.append(res)

    c._enqueue = cap

    await c.register_group(["G1"], True, None, operation_id="op1")

    ext = captured[-1].extensions["cyparta"]
    assert ext["subscribe"] is True
    assert ext["subscripe"] is True
    assert "subscribe" in ext["deprecationNotes"][0].lower() or "Prefer" in ext["deprecationNotes"][0]


@pytest.mark.asyncio
@override_settings(CYPARTA_WS_REQUIRE_AUTH=True)
async def test_subscribe_kwarg_overrides_subscripe_false():
    user = SimpleNamespace(is_anonymous=False, pk=1)
    c = _bare_consumer({"type": "websocket", "user": user})
    c._active_operation_id = "op1"
    c._enqueue = MagicMock()

    await c.register_group(
        ["G1"], False, None, operation_id="op1", subscribe=True
    )

    c.channel_layer.group_add.assert_awaited()


@pytest.mark.asyncio
@override_settings(CYPARTA_WS_REQUIRE_AUTH=True)
async def test_detect_register_group_status_passes_subscribe():
    user = SimpleNamespace(is_anonymous=False, pk=1)
    c = _bare_consumer({"type": "websocket", "user": user})
    c._active_operation_id = "op1"
    c._enqueue = MagicMock()
    c.register_group = AsyncMock()
    c.un_register_group = AsyncMock()

    await c.detect_register_group_status(
        ["G1"],
        subscripe=False,
        operation_id="op1",
        subscribe=True,
    )

    c.register_group.assert_awaited_once()
    assert c.register_group.await_args.kwargs.get("subscribe") is True
    c.un_register_group.assert_not_awaited()
