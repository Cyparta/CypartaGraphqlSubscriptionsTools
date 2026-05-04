import logging

from channels.layers import get_channel_layer
from django.core import serializers

from .serialize import serialize_value
from .utils import GroupNameInvalid, validate_group_name

logger = logging.getLogger(__name__)


async def trigger_subscription(group, value):
    # Get the channel layer
    channel_layer = get_channel_layer()

    try:
        group = validate_group_name(group)
    except GroupNameInvalid:
        logger.warning(
            "trigger_subscription skipped: group name failed validation",
            exc_info=False,
        )
        return

    # Send a message to the specified channel group
    await channel_layer.group_send(
        group,
        {
            "type": "subscription.triggered",  # Type of the message
            "value": await serialize_value(value, group),  # The value to be sent
            "group": group,  # The channel group to send the message to
        },
    )
