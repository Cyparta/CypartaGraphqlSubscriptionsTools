# Helper function to get model name instance

def get_model_name_instance(ModelType):
    return ModelType._meta.model.__name__



def filter_requested_fields(deserialized_data,requested_fields):
     
        exposed_fields = {field: deserialized_data['fields'][field] for field in requested_fields}
        deserialized_data['fields']=exposed_fields
        return deserialized_data