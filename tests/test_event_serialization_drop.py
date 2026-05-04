"""CYPARTA_WS_DROP_EVENT_ON_SERIALIZATION_ERROR and tuple passthrough."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from django.test import override_settings

from CypartaGraphqlSubscriptionsTools import events


@pytest.mark.asyncio
@override_settings(
    CYPARTA_WS_EVENT_SERIALIZER="tests.test_event_serializers.broken_serializer",
    CYPARTA_WS_DROP_EVENT_ON_SERIALIZATION_ERROR=True,
)
async def test_drop_true_skips_group_send_when_default_also_fails():
    layer = AsyncMock()
    with patch.object(events, "get_channel_layer", return_value=layer):
        with patch.object(events, "_default_event_serialize", side_effect=RuntimeError("x")):
            await events.trigger_subscription("ValidGroup", {"z": 1})
    layer.group_send.assert_not_awaited()


@pytest.mark.asyncio
@override_settings(CYPARTA_WS_DROP_EVENT_ON_SERIALIZATION_ERROR=False)
async def test_tuple_converted_to_list_on_fallback():
    layer = AsyncMock()
    with patch.object(events, "get_channel_layer", return_value=layer):
        with patch.object(events, "_default_event_serialize", side_effect=RuntimeError("x")):
            await events.trigger_subscription("ValidGroup", (1, (2, 3)))
    payload = layer.group_send.await_args.args[1]["value"]
    assert payload == [1, [2, 3]]
