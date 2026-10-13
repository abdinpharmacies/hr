---
name: node-service-workflow
description: Implement or debug a Node.js service endpoint, tracing validation, business logic, persistence, and error responses in the existing application.
---

Inspect package.json, the lockfile, runtime declaration, and an adjacent route
before editing. Use the project's existing framework, module system, validation,
authentication, and test runner.

Trace the requested behavior from the transport boundary through the service and
data layer. Validate untrusted inputs at that boundary and preserve the project's
authorization checks. Keep async failures observable through the existing error
handler. Avoid introducing a framework or changing the supported Node version as
an incidental part of endpoint work.

Test the changed success and failure paths with the existing runner. Report the
commands actually run and any external service that prevented verification.
