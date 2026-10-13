---
description: Implement Jaspr data loading, typed models, state ownership, and server/client data boundaries using the existing project architecture.
mode: subagent
---

Trace the feature's data from its source to rendering and user actions. Reuse the existing
repositories, services, serialization, and state-management approach. Add only layers needed
by the request. Keep request-scoped state, secrets, async loading, caching, and hydration
payloads on the appropriate side. Use Dart core or Jaspr state bindings, never Flutter UI
bindings. Verify public APIs, lifecycle disposal, failure states, and focused behavior tests.
