"""First-class ``subscribe=`` without positional ``subscripe``; deprecation gating."""

from __future__ import annotations

from collections import defaultdict
from types import SimpleNamespace

import pytest
from django.test import override_settings

from CypartaGraphqlSubscriptionsTools.consumers import (
    CypartaGraphqlSubscriptionsConsumer,
    OperationState,
)


def _bare(scope):
    c = object.__new__(CypartaGraphqlSubscriptionsConsumer)
    c.scope = scope
    from unittest.mock import AsyncMock, MagicMock

    c.channel_layer = MagicMock()
    c.channel_layer.group_add = AsyncMock()
    c.channel_layer.group_discard = AsyncMock()
    c.channel_name = "ch"
    c._group_ops = defaultdict(set)
    c._ops = {}
    c._active_subscription_field_name = "f"
    c._active_subscribe_variables = {}
    return c


@pytest.mark.asyncio
@override_settings(CYPARTA_WS_REQUIRE_AUTH=True)
async def test_register_group_subscribe_only_no_deprecation_notes():
    user = SimpleNamespace(is_anonymous=False, pk=1)
    c = _bare({"type": "websocket", "user": user})
    c._active_operation_id = "op1"
    captured = []

    def cap(oid, res):
        captured.append(res)

    c._enqueue = cap

    await c.register_group(["G1"], subscribe=True, operation_id="op1")

    ext = captured[-1].extensions["cyparta"]
    assert ext["subscribe"] is True
    assert "deprecationNotes" not in ext


@pytest.mark.asyncio
@override_settings(CYPARTA_WS_REQUIRE_AUTH=True)
async def test_detect_register_subscribe_only():
    user = SimpleNamespace(is_anonymous=False, pk=1)
    c = _bare({"type": "websocket", "user": user})
    c._active_operation_id = "op1"
    from unittest.mock import MagicMock

    c._enqueue = MagicMock()
    await c.detect_register_group_status(["G1"], subscribe=True, operation_id="op1")
    c.channel_layer.group_add.assert_awaited()


@pytest.mark.asyncio
@override_settings(CYPARTA_WS_REQUIRE_AUTH=True)
async def test_un_register_group_subscribe_false_only():
    user = SimpleNamespace(is_anonymous=False, pk=1)
    c = _bare({"type": "websocket", "user": user})
    c._active_operation_id = "op1"
    c._ops["op1"] = OperationState(None, {"G1"}, "f")
    c._group_ops["G1"].add("op1")
    captured = []

    c._enqueue = lambda oid, res: captured.append(res)

    await c.un_register_group(["G1"], subscribe=False, operation_id="op1")

    ext = captured[-1].extensions["cyparta"]
    assert ext["subscribe"] is False
    assert "deprecationNotes" not in ext
