# Changelog

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
