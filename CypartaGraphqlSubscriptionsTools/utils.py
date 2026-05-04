# Helper function to get model name instance

from channels.layers import BaseChannelLayer
from django.conf import settings


def get_model_name_instance(ModelType):
    return ModelType._meta.model.__name__


# Align with Django Channels ``BaseChannelLayer.valid_group_name`` (ASCII + length).
GROUP_NAME_MAX_LENGTH = BaseChannelLayer.MAX_NAME_LENGTH
GROUP_NAME_REGEX = BaseChannelLayer.group_name_regex
_ALLOWED_GROUP_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."
)


class GroupNameInvalid(ValueError):
    """Raised when ``validate_group_name`` rejects ``group_name`` (strict or unfixable)."""

    __slots__ = ("client_message",)

    def __init__(self, client_message: str):
        self.client_message = client_message
        super().__init__(client_message)


def _normalize_group_name_for_channels(name: str) -> str:
    """Map disallowed characters to ``_`` and enforce max length (``len < MAX``)."""
    out = "".join(ch if ch in _ALLOWED_GROUP_CHARS else "_" for ch in name)
    max_len = GROUP_NAME_MAX_LENGTH - 1
    if len(out) > max_len:
        out = out[:max_len]
    return out


def validate_group_name(group_name: str) -> str:
    """
    Validate (and optionally normalize) a Channels group name.

    Rules match ``channels.layers.BaseChannelLayer.valid_group_name``:
    non-empty unicode string, ``len(name) < GROUP_NAME_MAX_LENGTH``, characters
    ``[a-zA-Z0-9_.-]`` only.

    If ``CYPARTA_WS_STRICT_GROUP_NAMES`` is ``True`` (default), invalid names raise
    ``GroupNameInvalid`` with a generic ``client_message``. If ``False``, unsafe
    characters are replaced with ``_`` and the result is re-validated; unfixable
    inputs still raise ``GroupNameInvalid``.
    """
    strict = getattr(settings, "CYPARTA_WS_STRICT_GROUP_NAMES", True)
    if not isinstance(group_name, str):
        raise GroupNameInvalid("Invalid subscription channel name.")
    if strict:
        if (
            not group_name
            or len(group_name) >= GROUP_NAME_MAX_LENGTH
            or not GROUP_NAME_REGEX.match(group_name)
        ):
            raise GroupNameInvalid("Invalid subscription channel name.")
        return group_name

    if not group_name:
        raise GroupNameInvalid("Invalid subscription channel name.")
    normalized = _normalize_group_name_for_channels(group_name)
    if not normalized or not GROUP_NAME_REGEX.match(normalized):
        raise GroupNameInvalid("Invalid subscription channel name.")
    return normalized


def filter_requested_fields(deserialized_data, requested_fields):
    """
    Return subscription payload data, optionally filtering ``fields`` by name.

    Never mutates ``deserialized_data``. If ``requested_fields`` is ``None`` or
    empty, or the payload is not a dict / has no dict ``fields``, returns the
    input unchanged. When filtering applies, returns a new dict with a new
    ``fields`` mapping.
    """
    if not isinstance(deserialized_data, dict):
        return deserialized_data

    if requested_fields is None or (
        isinstance(requested_fields, (list, tuple, set)) and len(requested_fields) == 0
    ):
        return deserialized_data

    if "fields" not in deserialized_data:
        return deserialized_data

    fields = deserialized_data.get("fields")
    if not isinstance(fields, dict):
        return deserialized_data

    exposed_fields = {
        field: fields[field]
        for field in requested_fields
        if field in fields
    }
    out = dict(deserialized_data)
    out["fields"] = exposed_fields
    return out
