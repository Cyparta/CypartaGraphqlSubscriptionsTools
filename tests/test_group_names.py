"""Tests for ``validate_group_name`` and strict / non-strict modes."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from django.test import override_settings

from CypartaGraphqlSubscriptionsTools.utils import (
    GROUP_NAME_MAX_LENGTH,
    GroupNameInvalid,
    validate_group_name,
)


@override_settings(CYPARTA_WS_STRICT_GROUP_NAMES=True)
def test_strict_accepts_channels_safe_name():
    assert validate_group_name("MyModelUpdated.15") == "MyModelUpdated.15"


@override_settings(CYPARTA_WS_STRICT_GROUP_NAMES=True)
def test_strict_rejects_empty_and_non_string():
    with pytest.raises(GroupNameInvalid):
        validate_group_name("")
    with pytest.raises(GroupNameInvalid):
        validate_group_name("bad name")
    with pytest.raises(GroupNameInvalid):
        validate_group_name(123)  # type: ignore[arg-type]


@override_settings(CYPARTA_WS_STRICT_GROUP_NAMES=True)
def test_strict_rejects_too_long():
    s = "a" * (GROUP_NAME_MAX_LENGTH - 1)
    assert validate_group_name(s) == s
    with pytest.raises(GroupNameInvalid):
        validate_group_name("a" * GROUP_NAME_MAX_LENGTH)


@override_settings(CYPARTA_WS_STRICT_GROUP_NAMES=False)
def test_non_strict_normalizes_spaces_and_special_chars():
    assert validate_group_name("My Channel") == "My_Channel"


@override_settings(CYPARTA_WS_STRICT_GROUP_NAMES=False)
def test_non_strict_truncates_to_max_length():
    raw = "x" * (GROUP_NAME_MAX_LENGTH + 50)
    out = validate_group_name(raw)
    assert len(out) == GROUP_NAME_MAX_LENGTH - 1
    assert out == "x" * (GROUP_NAME_MAX_LENGTH - 1)


@pytest.mark.asyncio
@override_settings(CYPARTA_WS_STRICT_GROUP_NAMES=True)
async def test_trigger_subscription_does_not_group_send_invalid_name():
    from CypartaGraphqlSubscriptionsTools import events

    layer = AsyncMock()
    with patch.object(events, "get_channel_layer", return_value=layer):
        await events.trigger_subscription("bad group", {"payload": 1})
    layer.group_send.assert_not_awaited()
