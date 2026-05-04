# CypartaGraphqlSubscriptionsTools

Graphene + Django GraphQL **subscriptions** over **Django Channels** (async WebSockets). Supports **`graphql-transport-ws`** and **`graphql-ws`** via the `Sec-WebSocket-Protocol` header.

For background on the two protocols, see [GraphQL over WebSockets: subscription-transport-ws vs graphql-ws](https://wundergraph.com/blog/quirks_of_graphql_subscriptions_sse_websockets_hasura_apollo_federation_supergraph#graphql-subscriptions-over-websockets:-subscription-transport-ws-vs-graphql-ws).

---

## What you get (v4.1.4)

- **Per-connection bounded outbox** — `asyncio.Queue` + one sender task (slow clients cannot queue unbounded work). Configure with `CYPARTA_WS_OUTBOX_MAXSIZE` (default `256`) and optional **`CYPARTA_WS_OUTBOX_OVERFLOW_STRATEGY`** (`drop_newest`, `drop_oldest`, or `close_connection` with close code **4413**).
- **Multi-operation aware** — each client `subscribe` uses a transport **`id`**; groups and payloads are keyed per operation (`_ops` / `_group_ops`).
- **Live payload shape** — each event is sent as GraphQL `ExecutionResult` data shaped as **`{ "<responseKey>": value }`**, where **response key** is the subscription root field’s **alias** if present, otherwise the **field name** (from `graphql.parse`).
- **Register / unregister ack** — after joining or leaving groups, clients get a **`next`/`data`** message with **`data: null`** and **`extensions.cyparta`** (`action`, `registeredGroups`, **`subscribe`**, legacy **`subscripe`**, and **`deprecationNotes`** only when the legacy positional **`subscripe`** was used without **`subscribe=`**).
- **Channel group names** — validated against Django Channels rules before **`group_add`** / **`group_discard`** / **`group_send`** (see **`validate_group_name`** in `utils.py`; **`CYPARTA_WS_STRICT_GROUP_NAMES`** defaults to **`True`**).
- **Lifecycle helpers** — optional **`CypartaSubscriptionModelMixin`** schedules **`trigger_subscription`** on **`transaction.on_commit`** (no publish on rollback), per-group error isolation, and optional **`get_subscription_payload`**. Optional **`CYPARTA_WS_EVENT_SERIALIZER`** (cached by path), **`CYPARTA_WS_DROP_EVENT_ON_SERIALIZATION_ERROR`**, and **`CYPARTA_WS_RAISE_ON_INVALID_TRIGGER_GROUP`** for server-side publishes.

---

## Requirements

- Python **≥ 3.9**
- **Django**, **Graphene / graphene-django**, **Channels**, **django-lifecycle** (see `setup.py` / `requirements.txt` for pinned versions in this repo).

Install:

```bash
pip install cypartagraphqlsubscriptionstools
```

Or from source:

```bash
pip install -e .
```

The wheel includes only **`CypartaGraphqlSubscriptionsTools`** (and its empty **`migrations`** package). It does **not** ship demo models, demo GraphQL schema, or the **`examples/`** tree—those live in the repository for reference when you clone the project.

---

## Your models and schema (production)

1. **Models** — The library does **not** define tables. In your Django app (e.g. `myapp/models.py`), add normal models and optionally inherit **`CypartaSubscriptionModelMixin`** from **`CypartaGraphqlSubscriptionsTools.mixins`** so lifecycle hooks call **`trigger_subscription`** with the same group naming you use in subscription resolvers.

2. **GraphQL schema** — Define **`Query`**, **`Subscription`**, and **`schema = graphene.Schema(...)`** in your project (e.g. **`myapp/schema.py`**). Point **`GRAPHENE["SCHEMA"]`** at that module. Subscription resolvers use **`async_to_sync(root.detect_register_group_status)(...)`** as documented below.

3. **Demo copy-paste** — See **`examples/basic_django_app/`** in the repo for a minimal **`MyModel`** + **`schema.py`**. From a checkout you can add **`"examples.basic_django_app.apps.BasicDjangoAppConfig"`** to **`INSTALLED_APPS`** (see **`examples/README.md`**); this is not part of the PyPI wheel.

---

## 1. Install and enable the app

Add the app to **`INSTALLED_APPS`**:

```python
# settings.py
INSTALLED_APPS = [
    # ...
    "channels",
    "CypartaGraphqlSubscriptionsTools",
]
```

Configure **channel layers** (Redis for production; in-memory is fine for local dev):

```python
# settings.py
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}
```

Optional:

```python
# Max queued outbound messages per WebSocket before drops (default 256).
CYPARTA_WS_OUTBOX_MAXSIZE = 512

# Subscription group access (default: require authenticated scope["user"]).
CYPARTA_WS_REQUIRE_AUTH = True
# Optional dotted path to a class: one instance is cached per WebSocket connection.
# It must define:
#   has_permission(self, user, group_name, operation_id=None, scope=None, variables=None) -> bool
# (method may be sync or async). Group registration is all-or-nothing per call: if any
# requested group is denied, none of the groups in that call are joined.
# CYPARTA_WS_GROUP_PERMISSION_CLASS = "myapp.permissions.SubscriptionGroupPermission"

# Reject invalid channel group names (default True). When False, unsafe characters
# are normalized to underscores before join/send (still must yield a valid name).
CYPARTA_WS_STRICT_GROUP_NAMES = True

# Optional: dotted path to async or sync callable(value, group=None, scope=None)
# for channel payloads from trigger_subscription. Default uses serialize_value.
# CYPARTA_WS_EVENT_SERIALIZER = "myapp.ws.event_serialize.serialize_subscription_event"

# If True, trigger_subscription raises GroupNameInvalid on bad group names (default False).
# CYPARTA_WS_RAISE_ON_INVALID_TRIGGER_GROUP = False

# If True, skip group_send when both custom and default serialization fail (default False).
# CYPARTA_WS_DROP_EVENT_ON_SERIALIZATION_ERROR = False

# Outbox full policy: "drop_newest" (default), "drop_oldest", or "close_connection" (4413).
# CYPARTA_WS_OUTBOX_OVERFLOW_STRATEGY = "drop_newest"
```

### Recommended production settings

These are not defaults for every project, but they are a sensible baseline for locked-down, predictable behavior:

| Setting | Recommended | Why |
|--------|-------------|-----|
| **`CYPARTA_WS_REQUIRE_AUTH`** | **`True`** | Ensures subscription group joins map to an authenticated `scope["user"]` unless you intentionally expose public feeds. |
| **`CYPARTA_WS_STRICT_GROUP_NAMES`** | **`True`** | Rejects invalid Django Channels group strings at the boundary instead of normalizing unexpected input. |
| **`CYPARTA_WS_DROP_EVENT_ON_SERIALIZATION_ERROR`** | **`True`** | Avoids publishing payloads when both the custom serializer (if any) and **`serialize_value`** fail; the event is skipped and the failure is logged. |

**Outbox overflow strategy (`CYPARTA_WS_OUTBOX_OVERFLOW_STRATEGY`)** — pick based on how stale data should behave:

- **Dashboards / live metrics** — clients often only need the **latest** update. Prefer **`drop_oldest`**: when the outbox is full, the oldest queued message is discarded so newer ticks can be enqueued. Alternatively keep **`drop_newest`** and reduce **`CYPARTA_WS_OUTBOX_MAXSIZE`** if you prefer to drop only the newest overflow and retain older queued frames.
- **Chat / notification-style feeds** — usually keep the default **`drop_newest`** so a backlog of older messages is not silently discarded when one slow client fills the queue. If you only care about the most recent N messages, **`drop_oldest`** is also reasonable.
- **`close_connection`** — disconnects the socket (code **4413**) when the outbox is full; use when you want to shed pathological slow clients and force a reconnect rather than dropping silently.

Point **`ASGI_APPLICATION`** at your routing module (see below).

---

## 2. Wire ASGI and WebSocket routing

Mount **`CypartaGraphqlSubscriptionsConsumer`** on a URL your GraphQL WS client will use.

**Option A — reuse the package URL patterns**

```python
# your_project/routing.py
from channels.routing import URLRouter
from django.urls import path

from CypartaGraphqlSubscriptionsTools.routing import websocket_urlpatterns

# Or merge with your own patterns:
urlpatterns_websocket = [
    *websocket_urlpatterns,
    # path("ws/other/", OtherConsumer.as_asgi()),
]
```

**Option B — single explicit path**

```python
from django.urls import path
from CypartaGraphqlSubscriptionsTools.consumers import CypartaGraphqlSubscriptionsConsumer

websocket_urlpatterns = [
    path("graphql/", CypartaGraphqlSubscriptionsConsumer.as_asgi()),
]
```

**ASGI entry** (typical pattern):

```python
# your_project/asgi.py
import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "your_project.settings")
django_asgi_app = get_asgi_application()

from your_project.routing import urlpatterns_websocket  # adjust import

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(URLRouter(urlpatterns_websocket)),
})
```

```python
# settings.py
ASGI_APPLICATION = "your_project.asgi.application"
```

---

## 3. Point Graphene at your schema

The consumer runs subscriptions with **`graphene_settings.SCHEMA`**:

```python
# settings.py
GRAPHENE = {
    "SCHEMA": "your_project.schema.schema",
}
```

```python
# your_project/schema.py
import graphene

from your_app.graphql.subscriptions import Subscription as AppSubscription


class Query(graphene.ObjectType):
    hello = graphene.String()

    def resolve_hello(self, info):
        return "world"


class Subscription(AppSubscription):
    pass


schema = graphene.Schema(query=Query, subscription=Subscription)
```

---

## 4. WebSocket protocol (what the client must do)

1. **Negotiate subprotocol** — the handshake must include **`Sec-WebSocket-Protocol: graphql-transport-ws`** or **`graphql-ws`**. Unsupported values are rejected with close code **`1002`**.
2. **`connection_init`** — send first; the server replies with **`connection_ack`** and only then accepts **`subscribe`**. A second **`connection_init`** on the same socket is rejected with close code **`4429`**.
3. **`subscribe`** — must include a string **`id`** (GraphQL transport operation id). If **`subscribe`** arrives before **`connection_init`**, the socket is closed with **`4401`**.
4. **Ending an operation** — **`graphql-transport-ws`**: client sends **`complete`** with **`id`**; the server tears down that operation and replies with **`{"type": "complete", "id": "<id>"}`**. **`graphql-ws`** (Apollo legacy): client sends **`stop`** with **`id`**; the server still completes the operation with an outbound **`{"type": "complete", "id": "<id>"}`** (same as subscription-transport-ws). A **`complete`** / teardown message may be processed even before **`connection_init`** when an **`id`** is present.
5. **`ping` / `pong`** — on **`graphql-transport-ws`**, a client **`ping`** is answered with **`{"type": "pong"}`**; **`pong`** is ignored.
6. **`connection_terminate`** — closes the WebSocket (code **1000**).

Ping / keepalive: the server periodically sends **`ping`** (transport-ws) or **`ka`** (graphql-ws).

---

## 5. Writing subscription resolvers

Inside a subscription resolver, **`root`** is the **`CypartaGraphqlSubscriptionsConsumer`** instance. Join or leave channel groups with **`detect_register_group_status`**. Because the consumer is async, call it from sync Graphene code with **`async_to_sync`**:

```python
from asgiref.sync import async_to_sync
from CypartaGraphqlSubscriptionsTools.utils import get_model_name_instance
```

Typical pattern (preferred — keyword **`subscribe`** only):

```python
async_to_sync(root.detect_register_group_status)(
    [f"{model_name}Created"],
    requested_fields=requested_fields,
    variables=info.variable_values,
    subscribe=subscripe,   # map from your GraphQL argument name
)
```

Legacy positional **`subscripe`** remains supported as the second argument; **`deprecationNotes`** are sent only in that case when **`subscribe`** is not passed:

```python
async_to_sync(root.detect_register_group_status)(
    name_list,
    subscripe,           # optional positional: True = join, False = leave
    requested_fields=None,
    operation_id=None,
    variables=None,
    subscribe=None,     # if set, overrides positional ``subscripe``
)
```

**`requested_fields`** — when not `None` and non-empty, only those keys are kept under the serialized `fields` dict in the pushed payload (see `filter_requested_fields` in `utils.py`). The helper never mutates the event dict; invalid shapes are passed through unchanged.

**Group names** — must satisfy Django Channels naming rules (ASCII letters, digits, **`-`**, **`_`**, **`.`**, length strictly below **100**). Use **`validate_group_name`** from **`utils.py`** if you build names dynamically. Align names with **`trigger_subscription`** (see below). The mixin uses:

- `{ModelName}Created`
- `{ModelName}Updated.{pk}`
- `{ModelName}Deleted.{pk}`

### Example: model created

```python
import graphene
from asgiref.sync import async_to_sync
from graphene_django.types import DjangoObjectType

from CypartaGraphqlSubscriptionsTools.utils import get_model_name_instance
from your_app.models import MyModel


class MyModelType(DjangoObjectType):
    class Meta:
        model = MyModel


class Subscription(graphene.ObjectType):
    my_model_created = graphene.Field(MyModelType, subscripe=graphene.Boolean(required=True))

    def resolve_my_model_created(root, info, subscripe):
        requested_fields = [
            s.name.value for s in info.field_nodes[0].selection_set.selections
        ]
        model_name = get_model_name_instance(MyModelType)
        return async_to_sync(root.detect_register_group_status)(
            [f"{model_name}Created"],
            requested_fields=requested_fields,
            subscribe=subscripe,
        )
```

Use the same idea for **`Updated` / `Deleted`** with groups like `f"{model_name}Updated.{id}"` (match your client arguments and your **`trigger_subscription`** calls).

---

## 6. Model mixin (optional)

Subclass **`CypartaSubscriptionModelMixin`** so creates / updates / deletes emit channel events (requires **django-lifecycle** on the model). Publishes are scheduled with **`django.db.transaction.on_commit`**, so events are not sent if the surrounding transaction rolls back.

```python
# your_app/models.py
from django.db import models
from CypartaGraphqlSubscriptionsTools.mixins import CypartaSubscriptionModelMixin


class Article(CypartaSubscriptionModelMixin, models.Model):
    title = models.CharField(max_length=200)
```

Optional hooks (override on your model):

- **`should_publish_subscription_event(self, action: str) -> bool`** — `action` is **`"create"`**, **`"update"`**, or **`"delete"`**; return **`False`** to skip scheduling.
- **`get_subscription_group_names(self, action: str) -> list[str]`** — default names: **`{ModelName}Created`**, **`{ModelName}Updated.{pk}`**, **`{ModelName}Deleted.{pk}`**.
- **`get_subscription_payload(self, action: str)`** — value passed to **`trigger_subscription`** for each group (default **`self`**).

When **`CYPARTA_WS_EVENT_SERIALIZER`** changes at runtime (e.g. in tests), call **`CypartaGraphqlSubscriptionsTools.events.reset_event_serializer_cache()`** so the new dotted path is loaded.

---

## 7. Publishing events from your code

Use **`trigger_subscription`** to send a message to everyone in a channel group. Values that are **`models.Model`** instances are passed through **`serialize_value`** by default (JSON serialize + shape with `pk`, `fields`, optional `group`). Set **`CYPARTA_WS_EVENT_SERIALIZER`** to a dotted path for a custom **`(value, group=None, scope=None)`** callable (sync or async); errors are logged and the stack falls back to **`serialize_value`** then plain JSON-safe values where possible.

```python
from asgiref.sync import async_to_sync
from CypartaGraphqlSubscriptionsTools.events import trigger_subscription


async_to_sync(trigger_subscription)("MyModelCreated", instance)
```

Custom group names work as long as subscription resolvers register the same strings.

---

## 8. Optional WebSocket auth middleware

The package includes **`TokenAuthMiddleware`** (`Authorization: Token <key>` → sets `scope["user"]`). It expects **Django REST framework**’s **`Token`** model to be available if you use it:

```python
# asgi.py (excerpt)
from channels.auth import AuthMiddlewareStack
from channels.routing import URLRouter

from CypartaGraphqlSubscriptionsTools.middleware import TokenAuthMiddleware
from your_project.routing import urlpatterns_websocket

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        TokenAuthMiddleware(URLRouter(urlpatterns_websocket))
    ),
})
```

---

## 9. Upgrading from older releases

- **v4.1.4** — **`drop_oldest`** outbox path calls **`task_done()`** after **`get_nowait()`** (safe for future **`join()`**); overflow close scheduled at most once per socket; **`_safe_passthrough`** stringifies dict keys; README **Recommended production settings** (auth, strict names, drop-on-serialize-error, outbox strategy guidance).
- **v4.1.3** — Serializer import caching; **`CYPARTA_WS_DROP_EVENT_ON_SERIALIZATION_ERROR`**; mixin **`get_subscription_payload`** and per-group publish **`try`/`except`**; **`CYPARTA_WS_OUTBOX_OVERFLOW_STRATEGY`** for full outbox.
- **v4.1.2** — **`subscribe=`** can be used without positional **`subscripe`**. **`deprecationNotes`** only when legacy positional is used without **`subscribe`**. Mixin uses **`transaction.on_commit`** and **`after_delete`** (was **`before_delete`**). Optional **`CYPARTA_WS_EVENT_SERIALIZER`**, **`CYPARTA_WS_RAISE_ON_INVALID_TRIGGER_GROUP`**.
- **v4.1.1** — Channel group names are validated (`validate_group_name`, `CYPARTA_WS_STRICT_GROUP_NAMES`). Prefer the `subscribe` keyword on `detect_register_group_status` / `register_group` over `subscripe`; `extensions.cyparta` now includes `subscribe` (and still mirrors `subscripe`). A second `connection_init` on one socket closes with **4429**.
- **v4.1.0** — No bundled **`MyModel`**, package **`schema`**, or **`0001_initial`** migration; define models and **`GRAPHENE["SCHEMA"]`** in your project (or use **`examples/`** from a git checkout).
- **RxPY removed** — delivery uses a bounded queue + sender task.
- **Adapter settings removed** — no `CYPARTA_GRAPHQL_SUBSCRIPTION_ADAPTER`, `CYPARTA_LEGACY_SUBSCRIPTION_DATA`, or `adapt_channel_event`.
- **Register / unregister acks (v4.0.2+)** — restored as **`data: null`** + **`extensions.cyparta`** on the outbox (not mixed into Option B **`data`**). **`complete`** still ends an operation. (Unchanged in v4.1.0.)
- **Subscribe must include `id`**; **`connection_init`** before **`subscribe`** is enforced (**`4401`** if violated).
- **Payload data** uses **`{ responseKey: ... }`** (alias-aware) for live subscription events.

---

## Links

- [Django Channels installation](https://channels.readthedocs.io/en/latest/installation.html)
- [Channel layers](https://channels.readthedocs.io/en/latest/topics/channel_layers.html)
