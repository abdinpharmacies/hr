# Whole-system coverage

Read for a whole-system overview or a request for all components. Do not load for a focused screen, feature or function explanation. The retained [complete-system reference](../assets/complete-system-reference.png) supplies coverage categories, not a mandatory technology stack.

Check these categories against source, configuration and available runtime evidence:

| Category | What to establish |
| --- | --- |
| Clients | Browser, mobile, staff UI, their state and entry points |
| Proxy and ingress | DNS/TLS, reverse proxy, routing, load balancing, if present |
| Backend | Actual application/process boundaries, modules and APIs |
| Auth | Sessions/tokens, identity providers, authentication and authorization boundaries |
| Database and storage | Data ownership, relational stores, files/media, relevant backups |
| Cache | Browser, application, database or distributed caches; scope and invalidation |
| Queue and background work | Jobs, schedulers, workers, retry and execution paths |
| Containers | Whether processes are containerized; do not confuse C4 containers with Docker |
| Kubernetes or orchestration | Actual orchestration configuration, if any |
| Cloud and hosting | Observed hosting/runtime environment, not inferred vendor branding |
| CI/CD | Build, test, release and deployment path |
| Monitoring | Logs, metrics, traces, alerts and health checks |
| External integrations | Payments, messaging, legacy systems and direction of data exchange |

For each relevant category, record its actual component and purpose, relationships, evidence, and status: verified, inferred, not found in inspected sources, not applicable, or unverified. Do not label a category absent merely because its deployment configuration is outside the repository. Coverage is not a requirement to add Redis, Kafka, Kubernetes or a cloud vendor. An in-process cache or Odoo job mechanism can satisfy the corresponding role without another service.

Draw verified components with their actual names, grouped by role. Put unresolved infrastructure in a separate clearly labeled coverage note or table, not on the confirmed runtime path. Separate optional proposals from the current-state view. Include the client's entry path and the important business/data flow, not just an inventory of logos.

Keep operational/deployment connections distinguishable from runtime requests. Split a dense system into a runtime map and an operations/deployment view rather than hiding components or drawing an unreadable poster. Report inspection boundaries; claim complete coverage only for the declared scope and evidence.
