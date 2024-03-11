# Graphene CypartaGraphqlSubscriptionsTools

<p>
    <img src="https://sadakatcdn.cyparta.com/Cyparta/cover.jpg" alt="image">
    <a href="https://twitter.com/eslamelhadedy50">
        <img src="https://img.shields.io/twitter/follow/eslamelhadedy50?style=social&logo=twitter"
            alt="follow on Twitter"></a>
</p>

## Introduction

A CypartaGraphqlSubscriptionsTools implementation for Graphene + Django built using Django Channels +reactive programming in python (RxPY)
. Provides support for model creation, mutation and deletion,and get data with websocket or path list of events name for subscriptions .

libirary support Both WebSocket Protocol graphql-transport-ws and graphql-ws

for more info use full link : https://wundergraph.com/blog/quirks_of_graphql_subscriptions_sse_websockets_hasura_apollo_federation_supergraph#graphql-subscriptions-over-websockets:-subscription-transport-ws-vs-graphql-ws

libirary use async for more beast performance
# CypartaGraphqlSubscriptionsTools Features

1. **Real-time GraphQL Subscriptions:**
   - Enables real-time communication between GraphQL clients and servers using WebSocket connections.

2. **Support for Django Models:**
   - Integrates seamlessly with Django models, providing subscriptions for model creation, update, and deletion events.

3. **Django Subscription Model Mixin:**
   - Powerful mixin for Django models to enable real-time GraphQL subscriptions on instance lifecycle events.

4. **Dynamic Subscription Management:**
   - Flexible mechanism for managing subscriptions dynamically using parameters like `subscripe` and `id`.

5. **WebSocket Protocol Support:**
   - Supports both `graphql-transport-ws` and `graphql-ws` for compatibility with various GraphQL clients.

6. **Async Implementation:**
   - Leverages asynchronous programming for enhanced performance and suitability for high-concurrency applications.

7. **Custom Event Support:**
   - Allows creation of custom events and subscriptions, providing flexibility for handling events beyond Django signals.

8. **Observable and Reactive Programming:**
   - Utilizes `rxpy` for handling observables and reactive programming, enabling application of various operations on subscription streams.

9. **Multi-Subscription Support:**
   - Supports multiple subscriptions concurrently, allowing clients to subscribe to multiple events or models simultaneously.

10. **Easy Integration with Graphene:**
    - Seamless integration with the Graphene library for easy definition and management of GraphQL subscriptions.

11. **Ping Mechanism:**
    - Includes a ping mechanism to keep WebSocket connections alive and maintain communication between clients and servers.

12. **WebSocket Group Management:**
    - Provides functions for dynamically registering and unregistering WebSocket groups for organized subscription handling.

13. **In-memory Channel Layer Support:**
    - Supports an in-memory Channel Layer for development environments without the need for a dedicated Redis instance.

14. **Customizable Routing:**
    - Allows customization of WebSocket routing in Django channels, making it adaptable to various project structures.

15. **Compatibility with Django Lifecycle:**
    - Works seamlessly with the `django_lifecycle` library to leverage Django model lifecycle events.

## Installation

1. Install `CypartaGraphqlSubscriptionsTools`

   ```bash
   $ pip install django_lifecycle
   $ pip install CypartaGraphqlSubscriptionsTools
   ```

2. Add `CypartaGraphqlSubscriptionsTools` to `INSTALLED_APPS`:

   ```python
   # your_project/settings.py
   INSTALLED_APPS = [
       # ...
       'CypartaGraphqlSubscriptionsTools'
   ]
   ```

3. Add Django Channels to your project (see: [Django Channels installation docs](https://channels.readthedocs.io/en/latest/installation.html)) and set up [Channel Layers](https://channels.readthedocs.io/en/latest/topics/channel_layers.html). If you don't want to set up a Redis instance in your dev environment yet, you can use the in-memory Channel Layer:

   ```python
   # your_project/settings.py
   CHANNEL_LAYERS = {
       "default": {
           "BACKEND": "channels.layers.InMemoryChannelLayer"
       }
   }
   ```

4. Add `CypartaGraphqlSubscriptionsConsumer` to your `routing.py` file.

   ```python
   # your_project/routing.py
   from channels.routing import ProtocolTypeRouter, URLRouter
   from django.urls import path

   from CypartaGraphqlSubscriptionsTools.consumers import CypartaGraphqlSubscriptionsConsumer

   application = ProtocolTypeRouter({
       "websocket": URLRouter([
           path('graphql/', CypartaGraphqlSubscriptionsConsumer)
       ]),
   })
   ```

5. Define your subscriptions and connect them to your project schema

   ```python
   #your_project/schema.py
   import graphene
   from asgiref.sync import async_to_sync

   from your_app.graphql.subscriptions import YourSubscription


   class Query(graphene.ObjectType):
       base = graphene.String()


   class Subscription(YourSubscription):
       pass


   schema = graphene.Schema(
       query=Query,
       subscription=Subscription
   )
   ```

## Django Subscription Model Mixin

The Django Subscription Model Mixin is a powerful tool that seamlessly integrates with Django models to enable real-time GraphQL subscriptions when model instances are created, updated, or deleted. This mixin leverages the `django_lifecycle` library for managing model lifecycle events and the `CypartaGraphqlSubscriptionsTools` library for triggering GraphQL subscriptions.

### Usage

1. **Inherit from the `CypartaSubscriptionModelMixin` in Your Django Model:**

    ```python
    # your_project/models.py
    from CypartaGraphqlSubscriptionsTools.mixins import CypartaSubscriptionModelMixin

    class YourModel(CypartaSubscriptionModelMixin, models.Model):
        # Your model fields and methods go here
    ```

Replace `YourModel` with the actual name of your model. This mixin provides hooks for triggering subscriptions on model lifecycle events, such as creation, update, and deletion.

## Defining Subscriptions

Subscriptions in Graphene are defined as normal `ObjectType`'s. Each subscription field resolver must return an observable which emits values matching the field's type.

A simple hello world subscription (which returns the value `"hello world!"` every 3 seconds) could be defined as follows:

```python
import graphene
from rx import Observable

class Subscription(graphene.ObjectType):
    hello = graphene.String()

    def resolve_hello(root, info):
        return Observable.interval(3000) \
                         .map(lambda i: "hello world!")
```

## Responding to Model Events

Each subscription that you define will receive a an `Consumer` of `CypartaGraphqlSubscriptionsConsumer`'s as the `root` parameter, which will subscripe or cancel by `detect_register_group_status` function  .




### Model Created Subscriptions

This code snippet demonstrates how to implement GraphQL subscriptions for Django models using the CypartaGraphqlSubscriptionsTools library. In this example, a subscription named `mymodelcreated` is defined to trigger events whenever a new instance of the `MyModel` Django model is created. The `subscripe` parameter is introduced, allowing for dynamic subscription management by providing a boolean value (`True` to subscribe, `False` to cancel subscription).

# Code Explanation
-**GraphQL Type Definition**: The code defines a GraphQL type YourModelType using graphene and graphene_django.types.DjangoObjectType for the MyModel Django model.

-**Subscription Definition**: The Subscription class extends graphene.ObjectType and includes a subscription field named `get_my_model`. This field is associated with the MyModelType and includes the subscripe parameter to manage subscription status.

-**Subscription Resolver Logic**: The resolve_my_model_created function handles the resolution logic for the `get_my_model` subscription. It dynamically extracts requested fields from the GraphQL query using info.field_nodes and filters for the relevant fields. The event name is constructed based on the model name and the event type (`{model_name}Created`). The resolution logic is then delegated to the `detect_register_group_status` function.

Event Triggering: The event is triggered whenever a new instance of `MyModel` is created, leveraging the signals provided by `django_lifecycle`.

```python
import graphene
from graphene_django.types import DjangoObjectType
from CypartaGraphqlSubscriptionsTools.events import CREATED

from your_app.models import MyModel


class YourModelType(DjangoObjectType)
    class Meta:
        model = MyModel


class Subscription(graphene.ObjectType):
    get_my_model = graphene.Field(MyModelType, subscripe=graphene.Boolean())

    # Resolve function for handling 'get_my_model' based on 'subscripe'
    def resolve_get_my_model(root, info, subscripe):
        requested_fields = [field.name.value for field in info.field_nodes[0].selection_set.selections]
        model_name = get_model_name_instance(MyModelType)
        return async_to_sync(root.detect_register_group_status)([f'{model_name}Created'], subscripe, requested_fields)

```

### Model Updated Subscriptions

You can also filter events based on a subscription's arguments. For example, here's a subscription that fires whenever a model is updated:

```python
import graphene
from graphene_django.types import DjangoObjectType
from CypartaGraphqlSubscriptionsTools.events import UPDATED

from your_app.models import MyModel


class YourModelType(DjangoObjectType)
    class Meta:
        model = MyModel


class Subscription(graphene.ObjectType):
    my_model_updated = graphene.Field(MyModelType, id=graphene.String(), subscripe=graphene.Boolean())

    # Resolve function for handling 'my_model_updated' based on 'subscripe' and 'id'
    def resolve_my_model_updated(root, info, subscripe, id):
        model_name = get_model_name_instance(MyModelType)
        return async_to_sync(root.detect_register_group_status)([f'{model_name}Updated.{id}'], subscripe)
```

### Model Created Updated Deleted Subscriptions

You can also filter events based on a subscription's arguments. For example, here's a subscription that fires whenever a model is updated:

```python
import graphene
from graphene_django.types import DjangoObjectType
from CypartaGraphqlSubscriptionsTools.events import UPDATED

from your_app.models import MyModel


class YourModelType(DjangoObjectType)
    class Meta:
        model = MyModel


class Subscription(graphene.ObjectType):
    my_model_created_update_delete = graphene.Field(MyModelType, subscripe=graphene.Boolean(), id=graphene.String())

    # Resolve function for handling create, update, delete operations based on 'subscripe' and 'id'
    def resolve_my_model_created_update_delete(root, info, subscripe, id):
        requested_fields = [field.name.value for field in info.field_nodes[0].selection_set.selections]
        model_name = get_model_name_instance(MyModelType)
        groups = [f'{model_name}Created', f'{model_name}Updated.{id}', f'{model_name}Deleted.{id}']
        if id == "":
            groups = [f'{model_name}Created']

        return async_to_sync(root.detect_register_group_status)(groups, subscripe, requested_fields)


```

### Model Deleted Subscriptions

Defining a subscription that is fired whenever a given model instance is deleted can be accomplished like so

```python
import graphene
from graphene_django.types import DjangoObjectType
from CypartaGraphqlSubscriptionsTools.events import DELETED

from your_app.models import MyModel


class YourModelType(DjangoObjectType)
    class Meta:
        model = MyModel


class Subscription(graphene.ObjectType):
    my_model_deleted = graphene.Field(MyModelType, id=graphene.String(), subscripe=graphene.Boolean())

    # Resolve function for handling 'my_model_deleted' based on 'subscripe' and 'id'
    def resolve_my_model_deleted(root, info, subscripe, id):
        model_name = get_model_name_instance(MyModelType)
        return async_to_sync(root.detect_register_group_status)([f'{model_name}Deleted.{id}'], subscripe)
```

## Custom Events

To create a custom type in GraphQL using Graphene, you need to define a new class for your custom type by extending `graphene.ObjectType`. Let's say you want to create a custom type named `CustomType`. Here's an example:
```python

import graphene

class CustomType(graphene.ObjectType):
    # Define fields for your custom type
    field1 = graphene.String()
    field2 = graphene.Int()
    # Add more fields as needed

```
In this example, `CustomType` has two fields: `field1` of type `graphene.String()` and `field2` of type `graphene.Int()`. You can customize the fields based on the data you want to include in your custom type.

Now, you can use this `CustomType` in your `my_custom_event` subscription:

```python
import graphene

my_custom_event = graphene.Field(CustomType)

def resolve_my_custom_event(root, info, subscripe):
    return async_to_sync(root.detect_register_group_status)(['custom_event'], subscripe)



# elsewhere in your app:
from CypartaGraphqlSubscriptionsTools.events import trigger_subscription

async_to_sync(trigger_subscription)(f"{model_name}Created", self)
```
