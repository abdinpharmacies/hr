# EXPLAIN Cheatsheet

Quick-reference for reading query plans. Not a tutorial — a lookup table for Phase 2 diagnosis.

## How to Run

```sql
-- PostgreSQL: plan only (safe everywhere)
EXPLAIN <query>;

-- PostgreSQL: with execution stats (EXECUTES the query — use timeout guard)
BEGIN;
SET LOCAL statement_timeout = '3s';
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) <query>;
ROLLBACK;

-- PostgreSQL: JSON output (useful for tooling)
EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) <query>;

-- MySQL: basic plan
EXPLAIN <query>;

-- MySQL: detailed JSON (8.0+)
EXPLAIN FORMAT=JSON <query>;

-- MySQL: with execution stats (8.0.18+, EXECUTES the query)
-- WARNING: Only use on SELECT. For DML, EXPLAIN ANALYZE executes the mutation
-- and MySQL has no transaction-based guard to roll it back automatically.
EXPLAIN ANALYZE <SELECT query>;
```

## PostgreSQL Plan Nodes

Read bottom-up. Innermost/bottom nodes execute first.

### Scan Types

| Node | Meaning | When OK | When Bad |
|------|---------|---------|----------|
| Seq Scan | Full table scan | Small tables (<10K rows), or reading most rows | Large table + selective filter = missing index |
| Index Scan | B-Tree lookup + heap fetch | Selective queries (<10-15% of rows) | — |
| Index Only Scan | Index satisfies query, no heap | Best case for covered queries | High `Heap Fetches` = needs VACUUM |
| Bitmap Index Scan + Bitmap Heap Scan | Index builds bitmap, then batch-fetches | Medium selectivity, OR conditions | — |
| CTE Scan | Scans a WITH clause result | — | Large CTE materialized unnecessarily (PG <12) |
| Function Scan | Calls a set-returning function | — | Expensive function called per-row |

### Join Types

| Node | Meaning | When OK | When Bad |
|------|---------|---------|----------|
| Nested Loop | For each outer row, scan inner | Small outer set + indexed inner | Large outer set = O(n*m) |
| Hash Join | Build hash table on inner, probe with outer | Large-large equijoins | Hash too large for work_mem → disk spill |
| Merge Join | Both sides sorted, merge | Pre-sorted inputs (index) | Sort cost dominates if not pre-sorted |

### Sort & Aggregate

| Node | Meaning | Watch For |
|------|---------|-----------|
| Sort | Sorts rows | `Sort Method: external merge` = disk spill = slow |
| Incremental Sort | PG 13+, sorts on partial pre-order | Good — using existing index order |
| HashAggregate | Hash-based GROUP BY | Memory spill if groups exceed work_mem |
| GroupAggregate | Sort-based GROUP BY | Needs pre-sorted input |

### Other

| Node | Meaning | Watch For |
|------|---------|-----------|
| Materialize | Caches subplan result | Repeated scans of expensive subplan |
| SubPlan | Correlated subquery | Executes per outer row — rewrite as JOIN |
| Limit | Stops after N rows | Good if planner can push it down |
| Append | UNION ALL or partition scan | Check partition pruning is working |

### Key Metrics in EXPLAIN ANALYZE Output

| Metric | What to Check |
|--------|--------------|
| `actual time=X..Y` | X = time to first row, Y = time to last row (ms) |
| `rows=N` | Actual rows vs. plan's estimate. 10x+ mismatch = stale stats |
| `loops=N` | Node executed N times (inside nested loop). Multiply actual time × loops for true cost |
| `Buffers: shared hit=X read=Y` | hit = from cache, read = from disk. High `read` = cold cache or table too large |
| `Sort Method: quicksort Memory: Xkb` | In-memory sort (good) |
| `Sort Method: external merge Disk: Xkb` | Disk sort (bad — increase work_mem or add index) |
| `Heap Fetches: N` | On Index Only Scan: rows that needed heap access. High = table needs VACUUM |
| `Filter: ... (rows removed=N)` | Rows fetched but discarded. High N = filter not pushed to index |

## MySQL EXPLAIN Columns

| Column | Key Values | Meaning |
|--------|-----------|---------|
| type | `ALL` | Full table scan — usually bad on large tables |
| | `index` | Full index scan — better than ALL, still reads everything |
| | `range` | Index range scan — good |
| | `ref` | Index lookup by equality — good |
| | `eq_ref` | Unique index lookup (JOIN on PK/unique) — best for joins |
| | `const` | Single row by PK/unique — optimal |
| possible_keys | | Indexes the optimizer considered |
| key | | Index actually chosen. NULL = no index used |
| key_len | | Bytes of index used. Compare to full key length — partial use means composite index not fully utilized |
| rows | | Estimated rows to examine. Compare across query alternatives |
| filtered | | % of rows that pass the WHERE. Low % + high rows = inefficient filter |
| Extra | `Using index` | Covering index — no table access needed (good) |
| | `Using where` | Filter applied after fetch (check if index could do it) |
| | `Using temporary` | Temp table created (GROUP BY, DISTINCT, UNION) |
| | `Using filesort` | Sort not using index (may be fine for small sets) |
| | `Using index condition` | Index condition pushdown (ICP) — good, filter at storage engine |

## Red Flags Summary

Quick scan for problems — if you see any of these, dig deeper:

1. **Seq Scan / type=ALL** on table with >10K rows and selective WHERE
2. **rows estimate** off by 10x+ from actual (stale stats)
3. **Sort Method: external merge** or **Using filesort** on large result
4. **Using temporary** with large row count
5. **Nested Loop** with large outer set (check `loops=` value)
6. **Filter: rows removed** large number (filter not at index level)
7. **Heap Fetches** high on Index Only Scan (needs VACUUM)
8. **SubPlan** inside a loop (correlated subquery)
9. **Buffers: read** much higher than **hit** (working set doesn't fit in memory)
10. **key_len** much shorter than index definition (partial index use)
