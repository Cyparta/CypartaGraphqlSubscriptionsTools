import inspect
import logging

from channels.layers import get_channel_layer
from django.conf import settings
from django.utils.module_loading import import_string

from .serialize import serialize_value
from .utils import GroupNameInvalid, validate_group_name

logger = logging.getLogger(__name__)


def _safe_passthrough(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (dict, list, tuple)):
        return value
    return None


async def _default_event_serialize(value, group=None, scope=None):
    return await serialize_value(value, group)


async def _serialize_for_event(value, group=None, scope=None):
    path = str(getattr(settings, "CYPARTA_WS_EVENT_SERIALIZER", "") or "").strip()
    if not path:
        try:
            return await _default_event_serialize(value, group, scope)
        except Exception:
            logger.exception("default event serialization failed")
            return _safe_passthrough(value)

    try:
        fn = import_string(path)
    except Exception:
        logger.exception("CYPARTA_WS_EVENT_SERIALIZER import failed")
        try:
            return await _default_event_serialize(value, group, scope)
        except Exception:
            logger.exception("default event serialization failed after import error")
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
            return await _default_event_serialize(value, group, scope)
        except Exception:
            logger.exception("default event serialization failed after custom error")
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
        serialized = _safe_passthrough(value)

    payload = {
        "type": "subscription.triggered",
        "value": serialized,
        "group": group,
    }
    await channel_layer.group_send(group, payload)
