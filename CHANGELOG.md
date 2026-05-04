# Changelog

## 2.0.0

### Fixed

- **Per-connection `groups` registry** — `groups` is no longer a class attribute shared by all WebSocket connections (which caused cross-user overwrites and wrong deliveries).
- **Wire payload contract** — subscription pushes use `graphql.ExecutionResult` only. Channel events are mapped through **`adapt_channel_event`** (override on the consumer or set **`CYPARTA_GRAPHQL_SUBSCRIPTION_ADAPTER`** in Django settings).
- **`_send_result`** — includes `extensions` in the WebSocket `next` / `data` payload when present.

### Changed (breaking)

- **Registration ack** — no longer sends fake GraphQL `data` with `group-subscription` / `status`. Clients receive `data: null` and details under **`payload.extensions.cyparta`** (`registeredGroups`, `subscripe`, `action`).
- **Default channel events** — unless you implement **`adapt_channel_event`** (or **`CYPARTA_GRAPHQL_SUBSCRIPTION_ADAPTER`**), events are delivered under **`payload.extensions.cypartaSubscriptionEvent`** (serialized value), not as invalid top-level `data` with raw `pk` / `fields` / `group`.

### Migration

1. Subclass `CypartaGraphqlSubscriptionsConsumer` and override **`async def adapt_channel_event(self, operation_id, group, value, requested_fields)`** to return `ExecutionResult(data={"YourSubscriptionField": ...})`, **or** set **`CYPARTA_GRAPHQL_SUBSCRIPTION_ADAPTER`** to an async callable with the same signature.
2. For a temporary old wire shape, set **`CYPARTA_LEGACY_SUBSCRIPTION_DATA = True`** (not valid GraphQL field data; use only while migrating clients).
3. Update any client code that parsed registration messages from `payload.data` to read **`payload.extensions.cyparta`**.
