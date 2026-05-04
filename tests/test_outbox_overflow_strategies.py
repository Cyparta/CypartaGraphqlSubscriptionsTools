"""CYPARTA_WS_OUTBOX_OVERFLOW_STRATEGY behaviors."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from django.test import override_settings
from graphql import ExecutionResult

from CypartaGraphqlSubscriptionsTools.consumers import (
    CypartaGraphqlSubscriptionsConsumer,
    OutboundMessage,
)


@pytest.mark.asyncio
async def test_outbox_drop_oldest_removes_oldest_then_accepts_new():
    c = object.__new__(CypartaGraphqlSubscriptionsConsumer)
    CypartaGraphqlSubscriptionsConsumer.outbound_dropped_total = 0
    CypartaGraphqlSubscriptionsConsumer.outbox_overflow_drop_oldest_total = 0
    c._outbound_dropped = 0
    c._outbox_drop_oldest_count = 0
    c._outbox_overflow_close_count = 0
    c._outbox = asyncio.Queue(maxsize=2)
    for i in range(2):
        c._outbox.put_nowait(
            OutboundMessage(
                "1",
                ExecutionResult(data={"s": {"i": i}}, errors=None, extensions=None),
            )
        )
    with override_settings(CYPARTA_WS_OUTBOX_OVERFLOW_STRATEGY="drop_oldest"):
        CypartaGraphqlSubscriptionsConsumer._enqueue(
            c,
            "1",
            ExecutionResult(data={"s": {"i": 2}}, errors=None, extensions=None),
        )
    assert c._outbox.qsize() == 2
    got = {c._outbox.get_nowait().result.data["s"]["i"] for _ in range(2)}
    assert got == {1, 2}
    assert CypartaGraphqlSubscriptionsConsumer.outbox_overflow_drop_oldest_total >= 1


@pytest.mark.asyncio
async def test_drop_oldest_task_done_balances_unfinished_for_join():
    """Dropped oldest must call task_done() so asyncio.Queue.join() cannot hang."""
    c = object.__new__(CypartaGraphqlSubscriptionsConsumer)
    CypartaGraphqlSubscriptionsConsumer.outbound_dropped_total = 0
    CypartaGraphqlSubscriptionsConsumer.outbox_overflow_drop_oldest_total = 0
    c._outbound_dropped = 0
    c._outbox_drop_oldest_count = 0
    c._outbox_overflow_close_count = 0
    c._outbox_close_scheduled = False
    c._outbox = asyncio.Queue(maxsize=2)
    for i in range(2):
        c._outbox.put_nowait(
            OutboundMessage(
                "1",
                ExecutionResult(data={"s": {"i": i}}, errors=None, extensions=None),
            )
        )
    with override_settings(CYPARTA_WS_OUTBOX_OVERFLOW_STRATEGY="drop_oldest"):
        CypartaGraphqlSubscriptionsConsumer._enqueue(
            c,
            "1",
            ExecutionResult(data={"s": {"i": 2}}, errors=None, extensions=None),
        )
    while not c._outbox.empty():
        c._outbox.get_nowait()
        c._outbox.task_done()
    await asyncio.wait_for(c._outbox.join(), timeout=2.0)


@pytest.mark.asyncio
async def test_outbox_close_connection_schedules_close():
    c = object.__new__(CypartaGraphqlSubscriptionsConsumer)
    CypartaGraphqlSubscriptionsConsumer.outbox_overflow_close_connection_total = 0
    c._outbox_overflow_close_count = 0
    c._outbox_close_scheduled = False
    c._outbox = asyncio.Queue(maxsize=1)
    c._outbox.put_nowait(
        OutboundMessage(
            "1",
            ExecutionResult(data={"s": {"i": 0}}, errors=None, extensions=None),
        )
    )
    c.close = AsyncMock()
    with override_settings(CYPARTA_WS_OUTBOX_OVERFLOW_STRATEGY="close_connection"):
        CypartaGraphqlSubscriptionsConsumer._enqueue(
            c,
            "1",
            ExecutionResult(data={"s": {"i": 99}}, errors=None, extensions=None),
        )
    await asyncio.sleep(0.01)
    c.close.assert_awaited()
    assert c.close.await_args.kwargs.get("code") == 4413


@pytest.mark.asyncio
async def test_close_connection_overflow_schedules_close_only_once():
    c = object.__new__(CypartaGraphqlSubscriptionsConsumer)
    CypartaGraphqlSubscriptionsConsumer.outbox_overflow_close_connection_total = 0
    c._outbox_overflow_close_count = 0
    c._outbox_close_scheduled = False
    c._outbox = asyncio.Queue(maxsize=1)
    c._outbox.put_nowait(
        OutboundMessage(
            "1",
            ExecutionResult(data={"s": {"i": 0}}, errors=None, extensions=None),
        )
    )
    c.close = AsyncMock()
    created: list[asyncio.Task] = []
    loop = asyncio.get_running_loop()
    real_create_task = loop.create_task

    def capture_task(coro):
        t = real_create_task(coro)
        created.append(t)
        return t

    with patch.object(loop, "create_task", side_effect=capture_task):
        with override_settings(CYPARTA_WS_OUTBOX_OVERFLOW_STRATEGY="close_connection"):
            CypartaGraphqlSubscriptionsConsumer._enqueue(
                c,
                "1",
                ExecutionResult(data={"s": {"i": 1}}, errors=None, extensions=None),
            )
            CypartaGraphqlSubscriptionsConsumer._enqueue(
                c,
                "1",
                ExecutionResult(data={"s": {"i": 2}}, errors=None, extensions=None),
            )
    assert len(created) == 1
    for t in created:
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass
