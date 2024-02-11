# your_project/schema.py
import graphene
from graphene_django.types import DjangoObjectType
from CypartaGraphqlSubscriptionsTools.models import *
from asgiref.sync import async_to_sync
from .utils import get_model_name_instance
# Define DjangoObjectType for MyModel
class MyModelType(DjangoObjectType):
    class Meta:
        model = MyModel
class CustomType(graphene.ObjectType):
    # Define fields for your custom type
    field1 = graphene.String()
    field2 = graphene.Int()
    # Add more fields as needed


# Object type for handling subscriptions
class MyModelCreatedSubscription(graphene.ObjectType):
    get_my_model = graphene.List(MyModelType)

    # Resolve function for fetching all YourModel instances
    def resolve_get_my_model(root, info):
        print('root : ',root)
        print('type : ',type(root))
        requested_fields = [field.name.value for field in info.field_nodes[0].selection_set.selections]
        return MyModel.objects.all()

    my_model_created_update_delete = graphene.Field(MyModelType, subscripe=graphene.Boolean(), id=graphene.String())

    # Resolve function for handling create, update, delete operations based on 'subscripe' and 'id'
    def resolve_my_model_created_update_delete(root, info, subscripe, id):
        requested_fields = [field.name.value for field in info.field_nodes[0].selection_set.selections]
        model_name = get_model_name_instance(MyModelType)
        groups = [f'{model_name}Created', f'{model_name}Updated.{id}', f'{model_name}Deleted.{id}']
        if id == "":
            groups = [f'{model_name}Created']
        
        return async_to_sync(root.detect_register_group_status)(groups, subscripe, requested_fields)

    my_model_created = graphene.Field(MyModelType, subscripe=graphene.Boolean())

    # Resolve function for handling 'my_model_created' based on 'subscripe'
    def resolve_my_model_created(root, info, subscripe):
        requested_fields = [field.name.value for field in info.field_nodes[0].selection_set.selections]
        model_name = get_model_name_instance(MyModelType)
        return async_to_sync(root.detect_register_group_status)([f'{model_name}Created'], subscripe, requested_fields)

    my_model_updated = graphene.Field(MyModelType, id=graphene.String(), subscripe=graphene.Boolean())

    # Resolve function for handling 'my_model_updated' based on 'subscripe' and 'id'
    def resolve_my_model_updated(root, info, subscripe, id):
        model_name = get_model_name_instance(MyModelType)
        return async_to_sync(root.detect_register_group_status)([f'{model_name}Updated.{id}'], subscripe)

    my_model_deleted = graphene.Field(MyModelType, id=graphene.String(), subscripe=graphene.Boolean())

    # Resolve function for handling 'my_model_deleted' based on 'subscripe' and 'id'
    def resolve_my_model_deleted(root, info, subscripe, id):
        model_name = get_model_name_instance(MyModelType)
        return async_to_sync(root.detect_register_group_status)([f'{model_name}Deleted.{id}'], subscripe)

    my_custom_event = graphene.Field(CustomType, subscripe=graphene.Boolean())
    def resolve_my_custom_event(root, info, subscripe,):

        return async_to_sync(root.detect_register_group_status)(['custom_event'], subscripe)

# Query type for the base field
class Query(graphene.ObjectType):
    base = graphene.String()


# Subscription type using YourModelCreatedSubscription
class Subscription(MyModelCreatedSubscription):
    pass

# Creating the schema with query and subscription types
schema = graphene.Schema(
    query=Query,
    subscription=Subscription
)
