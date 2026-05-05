"""ASGI middleware: DRF token auth via ``Authorization`` header or query string."""

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework.authtoken.models import Token

_TOKEN_QUERY_KEYS = ("token", "auth", "authToken", "accessToken")


def _extract_token_key(scope) -> str | None:
    headers = dict(scope.get("headers", []))

    # 1) Header (highest priority)
    auth_header = headers.get(b"authorization")
    if auth_header:
        try:
            decoded = auth_header.decode("utf-8", errors="replace")
            parts = decoded.split()

            if len(parts) == 2 and parts[0].lower() == "token":
                token_key = parts[1].strip()
                if token_key:
                    return token_key
        except Exception:
            pass

    # 2) Query string
    raw_qs = scope.get("query_string") or b""

    try:
        qs = parse_qs(raw_qs.decode("utf-8"), keep_blank_values=False)

        for qkey in _TOKEN_QUERY_KEYS:
            values = qs.get(qkey)
            if not values:
                continue

            token_key = (values[0] or "").strip()
            if token_key:
                return token_key
    except Exception:
        pass

    return None


class TokenAuthMiddleware:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "websocket":
            return await self.inner(scope, receive, send)

        token_key = _extract_token_key(scope)

        if token_key:
            scope["user"] = await self.get_user(token_key)
        else:
            scope["user"] = AnonymousUser()

        return await self.inner(scope, receive, send)

    @database_sync_to_async
    def get_user(self, token_key):
        try:
            token = Token.objects.select_related("user").get(key=token_key)
            return token.user
        except Token.DoesNotExist:
            return AnonymousUser()
