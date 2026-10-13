# Ready API Notes and Pilot

Source: AGENTS.md Phase 0. The 300 requests/day, 7-day trial and localhost-only test-key details below are historical account observations, not verified current API limits. The source supplies no endpoint, schema, vendor documentation URL or credential. Inspect the authorized integration/account docs before implementing requests; do not invent endpoints or acquire credentials.

Pilot: manually select 100 products; log match confidence, unmatched/ambiguous cases, data provenance, incremental value, Arabic quality and scientific quality against E-Plus. Cache by stable matched identity/version and track expiry. Use rate-limited queues with bounded retries, backoff and manual cancellation. Ambiguous fuzzy matches require review. Keep Ready only if measured quality improves on internal data.

### Ready API Rules

Ready API is optional enrichment only.

Free plan constraints:

- 300 requests/day.
- 7-day trial.
- Localhost-only test key.

Ready API must be:

- Cached.
- Rate limited.
- Queue driven.
- Manually controlled.
- Never the source of truth.
- Never called during website page load.
- Never used for automatic full-catalog publishing.

### Matching Priority

Use this order for enrichment/matching:

1. Barcode.
2. `eplus_serial`.
3. Product code.
4. Scientific grouping.
5. Normalized product name.
6. Fuzzy match.

