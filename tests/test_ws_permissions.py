"""WebSocket subscription group permission tests."""

from __future__ import annotations

from collections import defaultdict
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import override_settings

from CypartaGraphqlSubscriptionsTools.consumers import CypartaGraphqlSubscriptionsConsumer


class AllowAllPermission:
    def has_permission(self, user, group_name, operation_id=None, scope=None, variables=None):
        return True


class DenyBlockedChannelPolicy:
    def has_permission(self, user, group_name, operation_id=None, scope=None, variables=None):
        return group_name != "blocked_channel"


class DenyNopeGroupPolicy:
    def has_permission(self, user, group_name, operation_id=None, scope=None, variables=None):
        return group_name != "nope_group"


class AsyncDenyPolicy:
    async def has_permission(self, user, group_name, operation_id=None, scope=None, variables=None):
        return group_name != "async_denied"


def _bare_consumer(scope):
    c = object.__new__(CypartaGraphqlSubscriptionsConsumer)
    c.scope = scope
    c.channel_layer = MagicMock()
    c.channel_layer.group_add = AsyncMock()
    c.channel_name = "test-ch"
    c._group_ops = defaultdict(set)
    c._ops = {}
    c._active_subscription_field_name = "subField"
    c._active_subscribe_variables = {"x": 1}
    return c


@pytest.mark.asyncio
@override_settings(CYPARTA_WS_REQUIRE_AUTH=True)
async def test_anonymous_denied_by_default_no_group_ops():
    c = _bare_consumer({"type": "websocket", "user": AnonymousUser()})
    c._active_operation_id = "op1"
    enqueued = []
    c._enqueue = lambda oid, res: enqueued.append(res)

    await c.register_group(["OrderUpdated.15"], True, None, operation_id="op1")

    c.channel_layer.group_add.assert_not_awaited()
    assert c._group_ops.get("OrderUpdated.15", set()) == set()
    assert any(r.errors for r in enqueued if r.errors)


@pytest.mark.asyncio
@override_settings(CYPARTA_WS_REQUIRE_AUTH=True)
async def test_authenticated_allowed_when_no_permission_class():
    user = SimpleNamespace(is_anonymous=False, pk=42)
    c = _bare_consumer({"type": "websocket", "user": user})
    c._active_operation_id = "op1"
    enqueued = []
    c._enqueue = lambda oid, res: enqueued.append(res)

    await c.register_group(["OrderUpdated.15"], True, None, operation_id="op1")

    c.channel_layer.group_add.assert_awaited_once_with("OrderUpdated.15", "test-ch")
    assert "op1" in c._group_ops["OrderUpdated.15"]
    assert not any(r.errors for r in enqueued if r.errors)


@pytest.mark.asyncio
@override_settings(
    CYPARTA_WS_REQUIRE_AUTH=True,
    CYPARTA_WS_GROUP_PERMISSION_CLASS="tests.test_ws_permissions.AllowAllPermission",
)
async def test_custom_permission_class_allows():
    user = SimpleNamespace(is_anonymous=False, pk=1)
    c = _bare_consumer({"type": "websocket", "user": user})
    c._active_operation_id = "op1"
    c._enqueue = MagicMock()

    await c.register_group(["AnyChannel"], True, None, operation_id="op1")

    c.channel_layer.group_add.assert_awaited_once_with("AnyChannel", "test-ch")
    assert "op1" in c._group_ops["AnyChannel"]


@pytest.mark.asyncio
@override_settings(
    CYPARTA_WS_REQUIRE_AUTH=True,
    CYPARTA_WS_GROUP_PERMISSION_CLASS="tests.test_ws_permissions.DenyBlockedChannelPolicy",
)
async def test_custom_permission_class_denies_sends_error_and_skips_group_add():
    user = SimpleNamespace(is_anonymous=False, pk=1)
    c = _bare_consumer({"type": "websocket", "user": user})
    c._active_operation_id = "op1"
    enqueued = []
    c._enqueue = lambda oid, res: enqueued.append(res)

    await c.register_group(
        ["allowed_group", "blocked_channel"], True, None, operation_id="op1"
    )

    ga = c.channel_layer.group_add
    assert ga.await_count == 1
    assert ga.await_args_list[0].args[0] == "allowed_group"
    assert c._group_ops.get("blocked_channel", set()) == set()
    assert "op1" in c._group_ops["allowed_group"]
    assert any(
        r.errors
        and any(
            "Not authorized" in getattr(e, "message", str(e)) for e in r.errors
        )
        for r in enqueued
        if r.errors
    )


@pytest.mark.asyncio
@override_settings(
    CYPARTA_WS_REQUIRE_AUTH=True,
    CYPARTA_WS_GROUP_PERMISSION_CLASS="tests.test_ws_permissions.DenyNopeGroupPolicy",
)
async def test_denied_group_not_in_group_ops():
    user = SimpleNamespace(is_anonymous=False, pk=1)
    c = _bare_consumer({"type": "websocket", "user": user})
    c._active_operation_id = "op1"
    c._enqueue = MagicMock()

    await c.register_group(["ok", "nope_group"], True, None, operation_id="op1")

    c.channel_layer.group_add.assert_awaited_once_with("ok", "test-ch")
    assert c._group_ops.get("nope_group", set()) == set()


@pytest.mark.asyncio
@override_settings(CYPARTA_WS_REQUIRE_AUTH=False)
async def test_require_auth_false_allows_anonymous_without_permission_class():
    c = _bare_consumer({"type": "websocket", "user": AnonymousUser()})
    c._active_operation_id = "op1"
    c._enqueue = MagicMock()

    await c.register_group(["PublicFeed"], True, None, operation_id="op1")

    c.channel_layer.group_add.assert_awaited_once_with("PublicFeed", "test-ch")
    assert "op1" in c._group_ops["PublicFeed"]


@pytest.mark.asyncio
@override_settings(
    CYPARTA_WS_REQUIRE_AUTH=True,
    CYPARTA_WS_GROUP_PERMISSION_CLASS="tests.test_ws_permissions.AsyncDenyPolicy",
)
async def test_async_has_permission_on_permission_class():
    user = SimpleNamespace(is_anonymous=False, pk=1)
    c = _bare_consumer({"type": "websocket", "user": user})
    c._active_operation_id = "op1"
    c._enqueue = MagicMock()

    await c.register_group(["fine", "async_denied"], True, None, operation_id="op1")

    assert c._group_ops.get("async_denied", set()) == set()
    assert "op1" in c._group_ops["fine"]


@pytest.mark.asyncio
@override_settings(CYPARTA_WS_REQUIRE_AUTH=True)
async def test_missing_scope_user_denied_like_anonymous():
    c = _bare_consumer({"type": "websocket"})
    c._active_operation_id = "op1"
    c._enqueue = MagicMock()

    await c.register_group(["AnyGroup"], True, None, operation_id="op1")

    c.channel_layer.group_add.assert_not_awaited()
