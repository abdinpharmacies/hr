# SQL Optimization Patterns

An agent skill for safe SQL query diagnosis, EXPLAIN analysis, index recommendations, and database health reviews. Works with PostgreSQL, MySQL, and MariaDB.

This is not a tutorial or a library — it's an **operational protocol** that tells an AI agent *how to optimize SQL without breaking things*, paired with ready-to-use reference templates and diagnostic scripts.

## What It Does

- **Diagnoses slow queries** through a structured protocol with safety gates
- **Interprets EXPLAIN plans** using a lookup-based cheatsheet (not generated on the fly)
- **Proposes fixes** from a library of proven patterns (N+1, pagination, subqueries, indexes, batch ops)
- **Runs health checks, index audits, security audits, and performance reviews** via self-contained read-only SQL scripts
- **Classifies every action by risk level** (L0-L4) and requires user approval before any database change

## Architecture

```
SKILL.md                    — Protocol: phases, safety gates, risk levels, escalation, delivery
references/
  discovery-queries.md      — Schema, index health, write pressure, co-resident queries
  explain-cheatsheet.md     — Plan node lookup, metrics, red flags
  fix-patterns.md           — N+1, pagination, subqueries, indexes, batch ops, upsert, windows
  monitoring-queries.md     — Top queries, table health, unused indexes, sessions
scripts/
  postgresql/               — health-check, index-audit, security-audit, performance-review
  mysql/                    — health-check, index-audit, security-audit, performance-review
  mariadb/                  — health-check, index-audit, security-audit, performance-review
```

**Three layers, each with a clear job:**

1. **SKILL.md** (protocol) — When, why, and how to act. Always loaded. Controls safety and phase routing.
2. **references/** (templates) — What to paste. Loaded per-phase. Saves tokens by avoiding regeneration of common SQL.
3. **scripts/** (diagnostics) — Run as-is. Self-contained L0 read-only SQL. Labeled output sections for structured parsing.

## Installation

### Claude Code

Add the skill to your project's `.claude/settings.json`:

```json
{
  "skills": [
    "/path/to/sql-optimization-patterns/SKILL.md"
  ]
}
```

Or install from a remote source if published:

```bash
claude skill add sql-optimization-patterns
```

### OpenAI Codex

Place the `agents/openai.yaml` and `SKILL.md` in your Codex agents directory, or reference them in your project configuration.

### Other Agents

The skill is tool-agnostic. Any agent that can read markdown instructions and execute SQL can use it:

1. Load `SKILL.md` as system instructions or a skill file.
2. Make the `references/` and `scripts/` directories accessible to the agent.
3. Provide a SQL execution interface (MCP database tool, CLI client, ORM, or direct connection).

## Usage

Once installed, the skill activates automatically when you ask the agent to:

- **Diagnose a slow query:** *"Why is this query slow?"*
- **Interpret an EXPLAIN plan:** *"What does this EXPLAIN output mean?"*
- **Propose a fix:** *"Fix this slow query"*
- **Run a health check:** *"How's the database doing?"*
- **Audit indexes:** *"Find unused or redundant indexes"*
- **Security review:** *"Audit database security"*
- **Periodic performance review:** *"Monthly performance review"*

The protocol routes each request to the minimum required phases — a simple EXPLAIN interpretation skips schema discovery, while a full fix proposal runs all six phases.

### Running Diagnostic Scripts Directly

The scripts in `scripts/` are standalone SQL files. You can run them outside the agent:

```bash
# PostgreSQL
psql -h localhost -U readonly -d mydb -f scripts/postgresql/health-check.sql

# MySQL
mysql -h localhost -u readonly -p mydb < scripts/mysql/index-audit.sql

# MariaDB
mysql -h localhost -u readonly -p mydb < scripts/mariadb/security-audit.sql
```

All scripts are **L0 (read-only)** — they never modify data. They require a role with access to metadata views (`pg_stat_*`, `information_schema`, `performance_schema`).

## Safety Model

Databases hold data you can't get back. This skill is deliberately cautious — it was designed under the assumption that an unreviewed optimization can cause more damage than a slow query.

Every action is classified before execution:

| Level | Type | Example | Requirement |
|-------|------|---------|-------------|
| L0 | Read-only | EXPLAIN, schema queries | Proceed freely |
| L1 | Advisory | Query rewrite suggestion | Proceed freely |
| L2 | Additive DDL | CREATE INDEX | User approval required |
| L3 | Mutative DDL | ALTER TABLE, DROP INDEX | User approval + rollback plan |
| L4 | Data mutation | UPDATE, DELETE, VACUUM FULL | User approval + backup + staging validation |

The agent will **never execute L2+ changes without asking first**.

Beyond risk levels, the protocol includes several layers of protection:

- **EXPLAIN ANALYZE restricted to SELECT** — `EXPLAIN ANALYZE` executes the statement it analyzes. The skill explicitly forbids using it on INSERT/UPDATE/DELETE to prevent accidental data mutation, and documents that MySQL has no transaction-based guard for this.
- **Environment verification** — The agent programmatically confirms whether it's connected to a primary or replica (`pg_is_in_recovery()`, `SHOW REPLICA STATUS`) rather than trusting labels alone.
- **Business context before action** — The protocol requires understanding *why* a query exists before proposing changes. Optimizing without context can silently break application logic.
- **Schema freshness gate** — Before executing any approved change, the agent re-checks that the schema hasn't changed since the initial analysis (migrations, other team members, CI).
- **Mandatory rollback plans** — Every L2+ proposal includes the exact SQL to reverse the change, the condition that triggers rollback, and a verification query.
- **Escalation stops** — The agent is required to stop and ask when it encounters ambiguity, unexpected privileges, cascading triggers, or anything it can't confidently explain.
- **Scripts are immutable** — Diagnostic scripts are validated read-only artifacts. The agent is forbidden from modifying them before execution.

### A note on verbosity

This means the agent will ask questions, request confirmations, and sometimes refuse to proceed until it has the context it needs. If you find this too conservative for your workflow, the protocol is yours to adjust — `SKILL.md` is a plain text file. You can relax gates, remove phases, or change risk levels to match your risk tolerance. The defaults are strict because the cost of getting it wrong on a live database is high.

## Integration with MCP Toolbox for Databases

If [Google's MCP Toolbox for Databases](https://googleapis.github.io/genai-toolbox/getting-started/introduction/) is available in your environment, the skill uses it as the execution layer. The Toolbox handles connectivity, pooling, and auth; this skill handles the intelligence — protocol, safety, patterns, and diagnostics. See `SKILL.md` for details.

## Engine Support

| Engine | Scripts | References | Minimum Version |
|--------|---------|------------|-----------------|
| PostgreSQL | 4 scripts | Full coverage | 12+ (some features 14+) |
| MySQL | 4 scripts | Full coverage | 8.0+ |
| MariaDB | 4 scripts | Full coverage | 10.5+ |

MariaDB has dedicated scripts — do not use MySQL scripts against MariaDB or vice versa.

## Contributing

Improvements are welcome. Fork, modify, and publish under your own license. If you redistribute the original work unmodified, include the copyright notice per the MIT License.

## License

[MIT License](LICENSE) — use at your own risk, attribution required.
