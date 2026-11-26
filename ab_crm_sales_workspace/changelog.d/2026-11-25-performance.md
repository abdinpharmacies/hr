# Bounded notifications, contact queries and page serialization

Current changes before commit:

- Add bounded v2 unread snapshots and targeted replacement/removal semantics while preserving legacy notifications and employee-specific read/alert evidence.
- Group alert counts once, apply read positions in ORM domains, and cache authorization only during the current request.
- Select inbox targets from activity aggregates and serialize only the requested page; batch page unread/channel counts and bound preview reads.
- Add indexed case-folded contact/phone search keys, reject forged key writes, and backfill through bounded native ORM recomputation without changing customer write timestamps before enabling the indexed path.
- Publish coalesced commit-backed invalidations on authorized users' private partner channels; recover authoritative snapshots on reconnect and retain polling.
- Preserve unread totals across v2 pages, reject stale employee/company responses and coalesce workspace refreshes.
- Add functional/browser regressions, maintain both Arabic field references and bump runtime version to 19.0.1.43.0.
- Keep full-scale staging acceptance deferred at the user's request; no runtime deployment.

Files changed:

- `__manifest__.py`, `models/__init__.py`
- `models/alerts.py`, `models/customer_streams.py`, `models/directory.py`
- `models/workspace.py`, `models/session.py`, `models/request_cache.py`, `models/invalidation.py`
- `static/src/session_service.js`, `static/src/workspace.js`, `static/src/feedback.js`
- `static/tests/notifications.test.js`, `tests/test_workspace.py`, `tests/test_branch_browser.py`
- `i18n/ar.po`, `i18n/ar_001.po`, `README.md`, `RELEASE.md`
- `changelog.d/2026-11-25-performance.md`
