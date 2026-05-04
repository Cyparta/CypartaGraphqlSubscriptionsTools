"""CYPARTA_WS_EVENT_SERIALIZER and safe fallbacks."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from django.test import override_settings

from CypartaGraphqlSubscriptionsTools import events


async def sample_custom_serializer(value, group=None, scope=None):
    if isinstance(value, dict):
        return {"custom": True, "group": group, "data": value}
    return value


def broken_serializer(value, group=None, scope=None):
    raise RuntimeError("boom")


@pytest.mark.asyncio
@override_settings(CYPARTA_WS_EVENT_SERIALIZER="tests.test_event_serializers.sample_custom_serializer")
async def test_custom_serializer_used_in_trigger():
    layer = AsyncMock()
    with patch.object(events, "get_channel_layer", return_value=layer):
        await events.trigger_subscription("ValidGroup", {"a": 1})
    layer.group_send.assert_awaited()
    call = layer.group_send.await_args
    assert call.args[1]["value"] == {
        "custom": True,
        "group": "ValidGroup",
        "data": {"a": 1},
    }


@pytest.mark.asyncio
@override_settings(CYPARTA_WS_EVENT_SERIALIZER="tests.test_event_serializers.broken_serializer")
async def test_broken_serializer_falls_back_for_plain_dict():
    layer = AsyncMock()
    with patch.object(events, "get_channel_layer", return_value=layer):
        await events.trigger_subscription("ValidGroup", {"x": 2})
    layer.group_send.assert_awaited()
    assert layer.group_send.await_args.args[1]["value"] == {"x": 2}


@pytest.mark.asyncio
async def test_plain_int_passes_through_default_serializer():
    layer = AsyncMock()
    with patch.object(events, "get_channel_layer", return_value=layer):
        await events.trigger_subscription("G", 42)
    assert layer.group_send.await_args.args[1]["value"] == 42
