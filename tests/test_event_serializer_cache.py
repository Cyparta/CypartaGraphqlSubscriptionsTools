"""Cache behavior for ``CYPARTA_WS_EVENT_SERIALIZER``."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from django.test import override_settings

from CypartaGraphqlSubscriptionsTools import events


@pytest.mark.asyncio
@override_settings(CYPARTA_WS_EVENT_SERIALIZER="tests.test_event_serializers.sample_custom_serializer")
async def test_import_string_not_called_twice_same_path():
    events.reset_event_serializer_cache()
    layer = AsyncMock()
    with patch.object(events, "get_channel_layer", return_value=layer):
        with patch(
            "CypartaGraphqlSubscriptionsTools.events.import_string"
        ) as imp:
            await events.trigger_subscription("G1", {"a": 1})
            await events.trigger_subscription("G2", {"b": 2})
    assert imp.call_count == 1


@pytest.mark.asyncio
async def test_cache_refreshes_when_setting_path_changes():
    events.reset_event_serializer_cache()
    layer = AsyncMock()
    with patch.object(events, "get_channel_layer", return_value=layer):
        with patch(
            "CypartaGraphqlSubscriptionsTools.events.import_string"
        ) as imp:
            with override_settings(
                CYPARTA_WS_EVENT_SERIALIZER="tests.test_event_serializers.sample_custom_serializer"
            ):
                await events.trigger_subscription("G", {})
            imp.reset_mock()
            with override_settings(
                CYPARTA_WS_EVENT_SERIALIZER="tests.test_event_serializers.broken_serializer"
            ):
                await events.trigger_subscription("G", {})
    assert imp.call_count == 1
