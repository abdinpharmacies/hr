# Recover polling and audit historical receipt reconciliation

## Committed baseline

- Commit: `200e8767caf0d3919b0f19e4a35e602ca42f0f07`
- Author: `Alhassan Hossny`
- Date: `2026-11-09T14:05:37+02:00`
- Original subject: `crm_messaging_gateway/docs: document dual-channel controls and queue recovery`

## Changes included in implementation commit `a89212d7`

- Classify sanitized reception errors and exit retryably after bounded temporary failures, retaining durable offsets and exclusive receiver ownership.
- Add per-account heartbeat freshness and backlog age without changing liveness/readiness contracts.
- Add explicit-ID preview/digest reconciliation, mandatory reasons and operator audits, preserving payloads and fingerprints across PostgreSQL and SQLite.
- Preserve preceding CRM, contact and POS-handoff work included in this update.

Files changed:
- `app/receiver.py`
- `app/telegram_setup.py`
- `app/health.py`
- `app/ops.py`
- `app/reconcile.py`
- `tests/test_reception_health.py`
- `tests/test_reconcile.py`
- `README.md`
