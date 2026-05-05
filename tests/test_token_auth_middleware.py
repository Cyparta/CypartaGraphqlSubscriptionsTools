"""Tests for ``TokenAuthMiddleware`` and ``_extract_token_key``."""

from __future__ import annotations

import pytest
from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework.authtoken.models import Token

from CypartaGraphqlSubscriptionsTools.middleware import (
    TokenAuthMiddleware,
    _extract_token_key,
)


def _ws_scope(*, headers=None, query_string=b""):
    return {
        "type": "websocket",
        "path": "/ws/graphql/",
        "headers": headers if headers is not None else [],
        "query_string": query_string,
    }


@pytest.mark.parametrize(
    "headers,query_string,expected",
    [
        (
            [(b"authorization", b"Token headerkey")],
            b"token=qskey",
            "headerkey",
        ),
        (
            [],
            b"token=onlyqs",
            "onlyqs",
        ),
        (
            [],
            b"auth=authqs",
            "authqs",
        ),
        (
            [],
            b"authToken=atk",
            "atk",
        ),
        (
            [],
            b"accessToken=ack",
            "ack",
        ),
    ],
)
def test_extract_token_key_header_and_query(headers, query_string, expected):
    scope = _ws_scope(headers=headers, query_string=query_string)
    assert _extract_token_key(scope) == expected


def test_extract_header_overrides_query_string():
    scope = _ws_scope(
        headers=[(b"authorization", b"Token winner")],
        query_string=b"token=loser",
    )
    assert _extract_token_key(scope) == "winner"


def test_extract_malformed_authorization_falls_through_to_query():
    scope = _ws_scope(
        headers=[(b"authorization", b"not-valid-token-format")],
        query_string=b"token=fromquery",
    )
    assert _extract_token_key(scope) == "fromquery"


def test_extract_malformed_authorization_no_query_returns_none():
    scope = _ws_scope(
        headers=[(b"authorization", b"Bearer only")],
        query_string=b"",
    )
    assert _extract_token_key(scope) is None


def test_extract_malformed_query_string_returns_none():
    scope = _ws_scope(headers=[], query_string=b"\xff\xfe\xff")
    assert _extract_token_key(scope) is None


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_header_token_resolves_user():
    User = get_user_model()
    user = await sync_to_async(User.objects.create_user)(
        username="huser", password="pass"
    )
    token = await sync_to_async(Token.objects.create)(user=user)

    scope = _ws_scope(
        headers=[(b"authorization", f"Token {token.key}".encode())],
    )
    captured = []

    async def inner(s, r, se):
        captured.append(s)

    await TokenAuthMiddleware(inner)(scope, None, None)
    assert captured[0]["user"].pk == user.pk


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_query_string_token_resolves_user():
    User = get_user_model()
    user = await sync_to_async(User.objects.create_user)(
        username="quser", password="pass"
    )
    token = await sync_to_async(Token.objects.create)(user=user)

    scope = _ws_scope(query_string=f"token={token.key}".encode())
    captured = []

    async def inner(s, r, se):
        captured.append(s)

    await TokenAuthMiddleware(inner)(scope, None, None)
    assert captured[0]["user"].pk == user.pk


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_header_overrides_query_for_user_resolution():
    User = get_user_model()
    user_a = await sync_to_async(User.objects.create_user)(
        username="usera", password="pass"
    )
    user_b = await sync_to_async(User.objects.create_user)(
        username="userb", password="pass"
    )
    tok_a = await sync_to_async(Token.objects.create)(user=user_a)
    tok_b = await sync_to_async(Token.objects.create)(user=user_b)

    scope = _ws_scope(
        headers=[(b"authorization", f"Token {tok_a.key}".encode())],
        query_string=f"token={tok_b.key}".encode(),
    )
    captured = []

    async def inner(s, r, se):
        captured.append(s)

    await TokenAuthMiddleware(inner)(scope, None, None)
    assert captured[0]["user"].pk == user_a.pk


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_invalid_token_returns_anonymous():
    scope = _ws_scope(
        headers=[(b"authorization", b"Token not-a-real-token-key-xxxxxxxx")],
    )
    captured = []

    async def inner(s, r, se):
        captured.append(s)

    await TokenAuthMiddleware(inner)(scope, None, None)
    assert isinstance(captured[0]["user"], AnonymousUser)


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_missing_token_returns_anonymous():
    scope = _ws_scope()
    captured = []

    async def inner(s, r, se):
        captured.append(s)

    await TokenAuthMiddleware(inner)(scope, None, None)
    assert isinstance(captured[0]["user"], AnonymousUser)


@pytest.mark.asyncio
async def test_non_websocket_passes_through_without_setting_user():
    scope = {"type": "http", "headers": [], "method": "GET"}
    seen = []

    async def inner(s, r, se):
        seen.append(s)
        return None

    await TokenAuthMiddleware(inner)(scope, None, None)
    assert seen[0] is scope
    assert "user" not in scope
