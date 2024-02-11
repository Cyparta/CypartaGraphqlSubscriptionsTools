
import json
import asyncio
from django.db import models
from django.core.serializers import serialize, deserialize
from django.core.serializers.base import DeserializationError


async def serialize_value(value,group=None):
    if isinstance(value, models.Model):
        serialized_data = await asyncio.to_thread(serialize, "json", [value])
        deserialized_data = json.loads(serialized_data)[0]
        deserialized_data['fields']['id'] = deserialized_data['pk']
       
        exposed_fields = deserialized_data['fields']
            #deserialized_data['model']
        return {'pk': deserialized_data['pk'], 'fields': exposed_fields,'group':group}

    return value




# async def deserialize_value(value):
#     try:
#         deserialized_data = await asyncio.to_thread(deserialize, "json", value)
#         return deserialized_data[0].object
#     except DeserializationError:
#         return json.loads(value)