---
name: sql-optimization-patterns
description: Diagnose slow Odoo PostgreSQL queries, review EXPLAIN plans and indexes, or inspect database health with bounded read-only SQL. Use for a specific performance or database review task in the Odoo profile; not for routine ORM edits or B-Connect SQL Server writes.
---

# SQL optimization for Odoo

Use the upstream [protocol](upstream-SKILL.md), [references](references/), and PostgreSQL [diagnostic scripts](scripts/postgresql/) as task-specific resources. Do not run all phases or scripts by default. The upstream MySQL and MariaDB material remains available for an explicitly named database, but the local Odoo database is PostgreSQL.

1. Read the project's `AGENTS.md`, identify the database and environment, and inspect the affected Odoo code and query before proposing changes. Prefer ORM batching, recordsets, and query reduction when they solve the issue. Do not bypass Odoo business logic to change inventory, pricing, or branch data.
2. Use `EXPLAIN` first. `EXPLAIN ANALYZE` executes its query: use it only for a bounded `SELECT` on an authorized environment, with an appropriate timeout. Check each upstream diagnostic script and its scope before running it; large catalog scans can still be costly.
3. Keep external B-Connect/E-Plus sources read-only. This package has no SQL Server diagnostic scripts, so do not run its PostgreSQL, MySQL, or MariaDB scripts against B-Connect.
4. For PostgreSQL changes, consider Odoo's module lifecycle and managed schema before adding indexes or DDL. Present the exact proposed SQL, affected tables, expected lock and write impact, rollback, and backup needs before any live schema or data change. Follow the user's authorization and environment approval controls. Never directly update system-managed stock quantities or business records through SQL.
5. Distinguish observed measurements from heuristic candidates. Verify plan changes and result equivalence on the correct branch scope. Do not recommend dropping an index from an unused-index counter alone.

The bundled `agents/openai.yaml` is Codex skill display metadata. This package does not define a subagent or an always-on rule.
