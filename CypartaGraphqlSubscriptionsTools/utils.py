# Helper function to get model name instance

def get_model_name_instance(ModelType):
    return ModelType._meta.model.__name__


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
