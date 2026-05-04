import inspect
import logging
from typing import Any

from channels.layers import get_channel_layer
from django.conf import settings
from django.utils.module_loading import import_string

from .serialize import serialize_value
from .utils import GroupNameInvalid, validate_group_name

logger = logging.getLogger(__name__)

_UNSET = object()
# Cached ``import_string`` result for ``CYPARTA_WS_EVENT_SERIALIZER`` (by dotted path).
_event_serializer_path: Any = _UNSET
_event_serializer_callable: Any = _UNSET

_SKIP_GROUP_SEND = object()


def reset_event_serializer_cache() -> None:
    """Clear the event-serializer import cache (e.g. after ``settings`` change in tests)."""
    global _event_serializer_path, _event_serializer_callable
    _event_serializer_path = _UNSET
    _event_serializer_callable = _UNSET


def _get_cached_event_serializer():
    """Return ``(path, fn)`` where ``fn`` is callable, ``False`` if import failed, or ``None`` if unset."""
    global _event_serializer_path, _event_serializer_callable
    path = str(getattr(settings, "CYPARTA_WS_EVENT_SERIALIZER", "") or "").strip()
    if _event_serializer_path is not _UNSET and path == _event_serializer_path:
        return path, _event_serializer_callable
    _event_serializer_path = path
    if not path:
        _event_serializer_callable = None
    else:
        try:
            _event_serializer_callable = import_string(path)
        except Exception:
            logger.exception("CYPARTA_WS_EVENT_SERIALIZER import failed")
            _event_serializer_callable = False
    return path, _event_serializer_callable


def _safe_passthrough(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, tuple):
        return [_safe_passthrough(v) for v in value]
    if isinstance(value, list):
        return [_safe_passthrough(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _safe_passthrough(v) for k, v in value.items()}
    return None


async def _default_event_serialize(value, group=None, scope=None):
    return await serialize_value(value, group)


async def _serialize_for_event(value, group=None, scope=None) -> Any:
    """
    Build the wire ``value`` for ``group_send``.

    Returns ``_SKIP_GROUP_SEND`` when ``CYPARTA_WS_DROP_EVENT_ON_SERIALIZATION_ERROR``
    is True and both custom and default serialization fail.
    """
    drop = bool(
        getattr(settings, "CYPARTA_WS_DROP_EVENT_ON_SERIALIZATION_ERROR", False)
    )
    path, fn = _get_cached_event_serializer()

    async def _try_default() -> Any:
        return await _default_event_serialize(value, group, scope)

    if fn is None or fn is False:
        try:
            return await _try_default()
        except Exception:
            logger.exception("default event serialization failed")
            if drop:
                logger.warning(
                    "subscription event dropped: serialization failed and "
                    "CYPARTA_WS_DROP_EVENT_ON_SERIALIZATION_ERROR is True",
                )
                return _SKIP_GROUP_SEND
            logger.warning(
                "subscription event using safe fallback after default serialization failed",
            )
            return _safe_passthrough(value)

    try:
        if inspect.iscoroutinefunction(fn):
            out = await fn(value, group=group, scope=scope)
        else:
            out = fn(value, group=group, scope=scope)
            if inspect.isawaitable(out):
                out = await out
        return out
    except Exception:
        logger.exception("CYPARTA_WS_EVENT_SERIALIZER callable failed")
        try:
            return await _try_default()
        except Exception:
            logger.exception("default event serialization failed after custom error")
            if drop:
                logger.warning(
                    "subscription event dropped: custom and default serialization failed "
                    "and CYPARTA_WS_DROP_EVENT_ON_SERIALIZATION_ERROR is True",
                )
                return _SKIP_GROUP_SEND
            logger.warning(
                "subscription event using safe fallback after custom and default "
                "serialization failed",
            )
            return _safe_passthrough(value)


async def trigger_subscription(group, value):
    channel_layer = get_channel_layer()
    raise_on_invalid = bool(
        getattr(settings, "CYPARTA_WS_RAISE_ON_INVALID_TRIGGER_GROUP", False)
    )

    try:
        group = validate_group_name(group)
    except GroupNameInvalid:
        if raise_on_invalid:
            raise
        logger.warning(
            "trigger_subscription skipped: group name failed validation",
            exc_info=False,
        )
        return

    try:
        serialized = await _serialize_for_event(value, group=group, scope=None)
    except Exception:
        logger.exception("event serialization failed before group_send")
        drop = bool(
            getattr(settings, "CYPARTA_WS_DROP_EVENT_ON_SERIALIZATION_ERROR", False)
        )
        if drop:
            logger.warning(
                "subscription event dropped: unexpected serialization error "
                "and CYPARTA_WS_DROP_EVENT_ON_SERIALIZATION_ERROR is True",
            )
            return
        serialized = _safe_passthrough(value)
        logger.warning(
            "subscription event using safe fallback after unexpected serialization error",
        )

    if serialized is _SKIP_GROUP_SEND:
        return

    payload = {
        "type": "subscription.triggered",
        "value": serialized,
        "group": group,
    }
    await channel_layer.group_send(group, payload)
