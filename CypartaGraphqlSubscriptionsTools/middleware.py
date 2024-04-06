# authentication/middleware.py

from channels.auth import AuthMiddlewareStack
from channels.db import database_sync_to_async
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import AnonymousUser

class TokenAuthMiddleware:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        headers = dict(scope["headers"])
        if b"authorization" in headers:
            try:
                auth_header = headers[b"authorization"].decode()
                _, token_key = auth_header.split(" ")
                user = await self.get_user(token_key)
                scope["user"] = user
            except Token.DoesNotExist:
                scope["user"] = AnonymousUser()
        return await self.inner(scope, receive, send)

    @database_sync_to_async
    def get_user(self, token_key):
        try:
            token = Token.objects.get(key=token_key)
            return token.user
        except Token.DoesNotExist:
            return AnonymousUser()
