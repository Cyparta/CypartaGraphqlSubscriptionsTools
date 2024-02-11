from channels.layers import get_channel_layer
from django.core import serializers
from .serialize import serialize_value
async def trigger_subscription(group, value):
    # Print some information for debugging purposes
    print('Value:', value)
    print('ID:', value.id)
    print('Group:', group)
    
    # Get the channel layer
    channel_layer = get_channel_layer()

    # Send a message to the specified channel group
    await channel_layer.group_send(
        group,
        {
            "type": "subscription.triggered",  # Type of the message
            "value": await serialize_value(value),  # The value to be sent
            "group": group  # The channel group to send the message to
        }
    )

    # Print a message indicating that the message has been sent
    
