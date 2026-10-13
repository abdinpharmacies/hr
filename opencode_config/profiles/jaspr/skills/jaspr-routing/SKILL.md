---
name: jaspr-routing
description: Implement or debug Jaspr routes, deep links, redirects, URL state, and navigation using the project router and rendering mode.
---

# Jaspr routing

Inspect rendering mode, installed router version, entrypoints, and current route definitions.
Reuse the project's router; when adding routing, choose a Jaspr-compatible package such as
`jaspr_router`. Do not substitute Flutter's `go_router` or `kaisel`.

Check installed route constructors, builders, redirects, and link APIs before using them.
Preserve real hrefs, browser history, query parameters, fragments, and URL encoding.
Use native anchors when appropriate and router links when their navigation behavior is
needed. Define not-found behavior and avoid redirect loops. Keep auth enforcement on the
server/API; a client redirect is only navigation behavior.

In server mode, verify direct requests to nested URLs and status codes. In static mode,
verify generated routes and hosting fallback requirements. In client mode, check refresh
and deep links with the actual dev/hosting server. Test back/forward and external links.
Do not deploy or change hosting configuration without task authorization.
