from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from django.test import override_settings

from CypartaGraphqlSubscriptionsTools import events
from CypartaGraphqlSubscriptionsTools.utils import GroupNameInvalid


@pytest.mark.asyncio
@override_settings(CYPARTA_WS_RAISE_ON_INVALID_TRIGGER_GROUP=True)
async def test_raise_on_invalid_trigger_group():
    layer = AsyncMock()
    with patch.object(events, "get_channel_layer", return_value=layer):
        with pytest.raises(GroupNameInvalid):
            await events.trigger_subscription("bad name", {})
    layer.group_send.assert_not_awaited()


@pytest.mark.asyncio
@override_settings(CYPARTA_WS_RAISE_ON_INVALID_TRIGGER_GROUP=False)
async def test_invalid_group_skips_when_not_raise():
    layer = AsyncMock()
    with patch.object(events, "get_channel_layer", return_value=layer):
        await events.trigger_subscription("bad name", {})
    layer.group_send.assert_not_awaited()
