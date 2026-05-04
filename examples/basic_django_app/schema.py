"""
Demo Graphene schema for ``examples.basic_django_app``.

Point ``GRAPHENE["SCHEMA"]`` at ``examples.basic_django_app.schema.schema`` when using this example app.
"""

import graphene
from asgiref.sync import async_to_sync
from graphene_django.types import DjangoObjectType

from CypartaGraphqlSubscriptionsTools.utils import get_model_name_instance

from .models import MyModel


class MyModelType(DjangoObjectType):
    class Meta:
        model = MyModel


class CustomType(graphene.ObjectType):
    field1 = graphene.String()
    field2 = graphene.Int()


class MyModelCreatedSubscription(graphene.ObjectType):
    get_my_model = graphene.List(MyModelType)

    def resolve_get_my_model(root, info):
        return MyModel.objects.all()

    my_model_created_update_delete = graphene.Field(
        MyModelType, subscripe=graphene.Boolean(), id=graphene.String()
    )

    def resolve_my_model_created_update_delete(root, info, subscripe, id):
        requested_fields = [
            field.name.value for field in info.field_nodes[0].selection_set.selections
        ]
        model_name = get_model_name_instance(MyModelType)
        groups = [
            f"{model_name}Created",
            f"{model_name}Updated.{id}",
            f"{model_name}Deleted.{id}",
        ]
        if id == "":
            groups = [f"{model_name}Created"]

        return async_to_sync(root.detect_register_group_status)(
            groups, subscripe, requested_fields, variables=info.variable_values
        )

    my_model_created = graphene.Field(MyModelType, subscripe=graphene.Boolean())

    def resolve_my_model_created(root, info, subscripe):
        requested_fields = [
            field.name.value for field in info.field_nodes[0].selection_set.selections
        ]
        model_name = get_model_name_instance(MyModelType)
        return async_to_sync(root.detect_register_group_status)(
            [f"{model_name}Created"],
            subscripe,
            requested_fields,
            variables=info.variable_values,
        )

    my_model_updated = graphene.Field(
        MyModelType, id=graphene.String(), subscripe=graphene.Boolean()
    )

    def resolve_my_model_updated(root, info, subscripe, id):
        model_name = get_model_name_instance(MyModelType)
        return async_to_sync(root.detect_register_group_status)(
            [f"{model_name}Updated.{id}"],
            subscripe,
            variables=info.variable_values,
        )

    my_model_deleted = graphene.Field(
        MyModelType, id=graphene.String(), subscripe=graphene.Boolean()
    )

    def resolve_my_model_deleted(root, info, subscripe, id):
        model_name = get_model_name_instance(MyModelType)
        return async_to_sync(root.detect_register_group_status)(
            [f"{model_name}Deleted.{id}"],
            subscripe,
            variables=info.variable_values,
        )

    my_custom_event = graphene.Field(CustomType, subscripe=graphene.Boolean())

    def resolve_my_custom_event(root, info, subscripe):
        return async_to_sync(root.detect_register_group_status)(
            ["custom_event"], subscripe, variables=info.variable_values
        )


class Query(graphene.ObjectType):
    base = graphene.String()


class Subscription(MyModelCreatedSubscription):
    pass


schema = graphene.Schema(query=Query, subscription=Subscription)
