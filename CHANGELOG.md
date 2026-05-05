# Changelog

## 4.1.6

### Added

- **`TokenAuthMiddleware`** (**`middleware.py`**) — authenticate WebSockets with **`Authorization: Token <key>`** (first) or query string **`token`**, **`auth`**, **`authToken`**, **`accessToken`**. Sets **`scope["user"]`** via **`Token.objects.select_related("user")`**, or **`AnonymousUser`** when absent/invalid. Tolerates malformed headers and query strings without raising.

### Documentation

- **README** — **WebSocket Authentication** section (browser vs header clients, examples, ASGI wiring).

### Tooling

- **`[test]`** extra includes **`djangorestframework`** for **`Token`** model tests.

## 4.1.5

### Documentation

- **README** — Full rewrite: installation, quick start (Channels / Graphene / ASGI), production settings table, Articles app example, permission class, custom event serializer, manual **`trigger_subscription`**, **graphql-transport-ws** and legacy **graphql-ws** client frames, group naming, authentication, payload filtering, troubleshooting, upgrade notes.
- **Packaging** — **`MANIFEST.in`** includes **`README.md`**, **`LICENSE`**, **`cover.jpg`**, **`graph.jpg`** so source distributions carry assets used on the project page.

## 4.1.4

### Fixed / hardened

- **Outbox `drop_oldest`** — after **`get_nowait()`**, call **`task_done()`** so **`asyncio.Queue`** unfinished-task accounting stays balanced (safe if **`join()`** is used later).
- **Outbox `close_connection`** — schedule at most one close per socket (**`_outbox_close_scheduled`**); overflow counters increment only when a close is actually scheduled.
- **`_safe_passthrough`** — dict keys are coerced with **`str(...)`** for JSON-safe wire payloads while preserving recursive value normalization.

### Documentation

- **README** — **Recommended production settings** table and guidance for **`CYPARTA_WS_OUTBOX_OVERFLOW_STRATEGY`** (dashboards vs chat vs **`close_connection`**).

### Tooling

- **`pytest-django`** in **`[test]`** extras and **`DJANGO_SETTINGS_MODULE`** in **`pytest.ini`** so **`@pytest.mark.django_db`** mixin tests run against migrated tables.

## 4.1.3

### Added

- **`CYPARTA_WS_EVENT_SERIALIZER` import cache** — dotted path is resolved once per path; use **`events.reset_event_serializer_cache()`** when settings change in tests or at runtime.
- **`CYPARTA_WS_DROP_EVENT_ON_SERIALIZATION_ERROR`** (default **`False`**) — when **`True`**, failed custom and default serialization skips **`group_send`**. Tuple (and nested) payloads in the safe fallback are normalized to lists. Clearer warnings when falling back after errors.
- **`get_subscription_payload(action)`** on **`CypartaSubscriptionModelMixin`** — default **`self`**; **`trigger_subscription`** receives this value. After-commit publishes wrap each group in its own **`try`/`except`** so one failure does not block others.
- **`CYPARTA_WS_OUTBOX_OVERFLOW_STRATEGY`** — **`drop_newest`** (default, prior behavior), **`drop_oldest`**, or **`close_connection`** (close with code **4413**). Class counters **`outbox_overflow_drop_oldest_total`**, **`outbox_overflow_close_connection_total`**, plus per-socket counters.

## 4.1.2

### Added

- **`subscribe` first-class** — `detect_register_group_status`, `register_group`, and `un_register_group` accept calls with only **`subscribe=`** (positional **`subscripe`** optional). **`deprecationNotes`** in **`extensions.cyparta`** appear only when the legacy positional **`subscripe`** is used and **`subscribe`** is not passed.
- **`CypartaSubscriptionModelMixin`** — publishes via **`transaction.on_commit`** so rolled-back transactions do not emit events. Hooks **`should_publish_subscription_event(action)`** and **`get_subscription_group_names(action)`**; create/update use **`after_*`** hooks; delete uses **`after_delete`** (was **`before_delete`**) so the row is gone only after commit while **`pk`** remains on the instance for default group names.
- **`CYPARTA_WS_EVENT_SERIALIZER`** — optional dotted path to a callable **`(value, group=None, scope=None)`** (sync or async); default remains **`serialize_value`**. Serialization failures are logged; safe fallbacks for plain JSON-like values.
- **`CYPARTA_WS_RAISE_ON_INVALID_TRIGGER_GROUP`** (default **`False`**) — when **`True`**, **`trigger_subscription`** raises **`GroupNameInvalid`** on invalid group names instead of skipping.

## 4.1.1

### Added

- **`validate_group_name`** / **`GroupNameInvalid`** in **`utils.py`** — channel group names are checked against Django Channels rules (same as **`BaseChannelLayer.valid_group_name`**) before **`group_add`**, **`group_discard`**, and **`group_send`** (including **`trigger_subscription`**). Setting **`CYPARTA_WS_STRICT_GROUP_NAMES`** (default **`True`**) rejects invalid names with a generic GraphQL error; when **`False`**, unsafe characters are normalized to **`_`** where possible.
- **`subscribe`** keyword argument on **`detect_register_group_status`**, **`register_group`**, and **`un_register_group`** — preferred over the legacy positional **`subscripe`** flag. **`extensions.cyparta`** now includes **`subscribe`**, still mirrors **`subscripe`**, and may include **`deprecationNotes`**.
- **Duplicate `connection_init`** — second init on the same WebSocket is rejected with close code **`4429`**.

## 4.1.0

### Removed (breaking)

- **Demo `MyModel`** and **`CypartaGraphqlSubscriptionsTools/migrations/0001_initial`** — the installable app no longer defines concrete models or ships migrations for them.
- **`CypartaGraphqlSubscriptionsTools.schema`** — removed; define schema in your project (see **`examples/basic_django_app/schema.py`** in the repo).
- **`consumers`** no longer imports **`CypartaGraphqlSubscriptionsTools.models`**.

### Changed

- **`views.graphql_token_view`** uses **`graphene_settings.SCHEMA`** from **`GRAPHENE["SCHEMA"]`** instead of importing a package-level schema module.
- **`setup.py`** lists explicit packages only (core app + migrations); **`examples/`** and **`tests/`** are not installed as top-level site-packages.
- **`CYPARTA_WS_GROUP_PERMISSION_CLASS`** — load a class by dotted path, **instantiate once per WebSocket connection** (cached), and call **`has_permission(self, user, group_name, operation_id=None, scope=None, variables=None)`** (sync or async). Import or **`has_permission`** errors deny the subscription, log a server-side traceback, and surface a generic GraphQL error (no group names or private IDs in the client message). **`CYPARTA_WS_GROUP_PERMISSION_CALLBACK`** and static **`can_subscribe_to_group`** on the permission class are not supported.
- **Group registration** — all-or-nothing per **`detect_register_group_status`** / **`register_group`** call: if any group in **`name_list`** is denied, **none** of those groups are joined for that operation; **`_group_ops`** / **`state.groups`** stay consistent; one GraphQL error is emitted.
- **`filter_requested_fields`** — no in-place mutation; returns the input unchanged when **`requested_fields`** is **`None`** or empty, when the payload is not a dict, or when **`fields`** is missing or not a dict.
- **WebSocket control messages** — **`ping`** → **`pong`**; **`pong`** ignored; **`connection_terminate`** closes the socket (**1000**).
- **Operation teardown** — outbound completion uses the protocol’s server frame (**`complete`**) rather than the client’s legacy **`stop`** type.

## 4.0.2

### Added

- **Register / unregister acknowledgements** — after `register_group` / `un_register_group`, the consumer enqueues a **`next`/`data`** message with **`data: null`** and **`extensions.cyparta`** (`action`: **`register`** / **`unregister`**, `registeredGroups`, `subscripe`). Live channel events remain **Option B** on **`data`** only (`extensions` null).

## 4.0.1

### Documentation

- **README** — rewritten as a practical setup and usage guide (ASGI routing, protocols, resolvers, mixin, `trigger_subscription`, optional auth middleware).

### Fixed / hardened

- **WebSocket protocol** — `connection_init` must precede `subscribe` (close **4401** otherwise); `complete` still honored when `id` is present without prior init.
- **`send_ping`** — handle send failures and cancellation so the ping task exits cleanly after disconnect.
- **`receive_json`** — dispatch on `message_type = request.get("type")` with explicit branches; unknown types log a warning.

### Tests

- Coverage for alias response keys, subscribe-before-init, unknown message types, and ping task behavior when `send_json` fails.

## 4.0.0

### Removed (breaking)

- **RxPY / `reactivex`** — subscriptions use a bounded **`asyncio.Queue`** and a single **sender task** per WebSocket.
- **`CYPARTA_GRAPHQL_SUBSCRIPTION_ADAPTER`**, **`CYPARTA_LEGACY_SUBSCRIPTION_DATA`**, **`adapt_channel_event`**, **`default_adapt_channel_event`**.
- **`self.id`** as implicit routing for subscribe handling; transport **`id`** is required on each **`subscribe`** message.
- **Registration ack** — no synthetic **`next`** payloads for register/unregister; only real channel events are enqueued. **`complete`** is still sent when the client or server ends an operation.

### Added

- **`OperationState`** (`requested_fields`, `groups`, **`subscription_field_name`**) and registries **`_ops`** / **`_group_ops`**.
- **`complete`** handling: unregister one operation, **`group_discard`** when ref-count hits zero, outbound **`{"type":"complete","id"}`**.
- **`CYPARTA_WS_OUTBOX_MAXSIZE`** (default **256**) for per-socket outbox bound; **`outbound_dropped_total`** + per-connection drop counter on **`QueueFull`**.
- **Subscription root field** detection via **`graphql.parse`** (fallback string if parse fails).
- **Unsupported `Sec-WebSocket-Protocol`**: connection closed with **1002** before accept (no ping task).

### Changed

- **Outbound event `data`** shape (Option B): **`{ "<subscription_field_name>": <payload> }`** (e.g. **`myModelUpdated`**) instead of raw dict or **`extensions.cypartaSubscriptionEvent`**.
- **`disconnect`**: no **`websocket.close`** JSON; ping and outbox sender tasks cancelled with **`asyncio.CancelledError`** suppressed where appropriate.

## 3.0.2

### Fixed

- **PyPI upload** — pin build-time setuptools to **`>=61,<75`** in **`pyproject.toml`** so wheels use **Metadata-Version 2.1** (avoids **2.4** / **`Dynamic: license-file`** rejected by **`twine check`** / PyPI as *unrecognized or malformed field `license-file`*). Use **`license="MIT"`** in **`setup.py`** instead of the filename **`LICENSE`**.

## 3.0.1

Maintenance release (version bump for distribution; same behavior as **3.0.0**).

## 3.0.0

### Removed

- **`CYPARTA_GRAPHQL_SUBSCRIPTION_ADAPTER`** — channel events are always wrapped as **`ExecutionResult(data=serialized_value, ...)`** and pushed on **`payload.data`** (same as pre-adapter behavior). Subclass the consumer if you need custom shaping.

## 2.3.0

### Removed

- **`adapt_channel_event`** / **`default_adapt_channel_event`** — replaced by optional **`CYPARTA_GRAPHQL_SUBSCRIPTION_ADAPTER`** (removed again in **3.0.0**).

## 2.2.0

### Removed

- **`CYPARTA_LEGACY_SUBSCRIPTION_DATA`** — single default wire shape: serialized channel payload on **`payload.data`**.

## 2.1.0

### Changed

- **Default channel events on `data`** — `default_adapt_channel_event` put the serialized channel payload on **`payload.data`** by default; **`CYPARTA_LEGACY_SUBSCRIPTION_DATA = False`** could still select the extensions-only path (removed in **2.2.0**).

## 2.0.0

### Fixed

- **Per-connection `groups` registry** — `groups` is no longer a class attribute shared by all WebSocket connections (which caused cross-user overwrites and wrong deliveries).
- **Wire payload contract** — subscription pushes use `graphql.ExecutionResult` for WebSocket payloads.
- **`_send_result`** — includes `extensions` in the WebSocket `next` / `data` payload when present.

### Changed (breaking)

- **Registration ack** — no longer sends fake GraphQL `data` with `group-subscription` / `status`. Clients receive `data: null` and details under **`payload.extensions.cyparta`** (`registeredGroups`, `subscripe`, `action`).
- **Default channel events (2.0.0)** — events were delivered under **`payload.extensions.cypartaSubscriptionEvent`** (serialized value), not as top-level `data` with raw `pk` / `fields` / `group`. Later releases put the dict on **`payload.data`** by default.

### Migration

1. Update any client code that parsed registration messages from `payload.data` to read **`payload.extensions.cyparta`**.
