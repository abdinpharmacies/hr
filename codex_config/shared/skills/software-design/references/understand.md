# Understand existing software

Start at the entry point relevant to the question: UI event, route, command, job, or subscription. Follow calls and data/state changes through direct collaborators. Inspect manifests, configuration and deployment definitions only as needed to identify real runtime boundaries.

For a client, identify view/widget ownership, state lifetime, events, effects, repositories, cache and network boundaries. For a backend, identify entry points, application responsibilities, data ownership and external integrations. An import or package dependency is not proof of a runtime network call. An Odoo addon or Flutter package is not an independently deployed service merely because it has a manifest.

For each important relationship record the source, target, operation/data, direction, synchronous or asynchronous behavior, and evidence. Add protocol, read/write access, errors and trust boundaries where relevant. Mark missing evidence rather than drawing an invented edge. Separate development configuration from deployed observations.

Use context/container views for a whole system; component, sequence, state or data-flow views for a feature. Explain what each part does and why it is relevant to this flow. Historical reasons require documentation, decision records or history; otherwise label the rationale as inference.

For a requested repository-wide architecture report, read [Repository analysis](repository-analysis.md). For a focused question, inspect source directly without running the analyzer. Never equate an empty detector result with a healthy or empty system.

For a whole-system overview or a request to cover every component, read [Whole-system coverage](system-coverage.md). Account for each relevant category without inventing services; focused requests do not need this checklist.
