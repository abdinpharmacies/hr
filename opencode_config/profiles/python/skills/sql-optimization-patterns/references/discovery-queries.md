# Discovery Queries

Ready-to-run templates for Phase 1 (Context Acquisition) and Phase 3 (Multi-Query Impact Analysis). Replace `<table>` with the target table name.

## Schema Discovery

### PostgreSQL

```sql
-- Table structure
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = '<table>'
ORDER BY ordinal_position;

-- Foreign keys (outgoing)
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = '<table>'::regclass AND contype = 'f';

-- Foreign keys (incoming — other tables referencing this one)
SELECT conname, conrelid::regclass AS referencing_table, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE confrelid = '<table>'::regclass AND contype = 'f';

-- Existing indexes with definitions
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = '<table>';

-- Table size, index size, row estimate
SELECT
    pg_size_pretty(pg_relation_size('<table>')) AS table_size,
    pg_size_pretty(pg_indexes_size('<table>')) AS indexes_size,
    pg_size_pretty(pg_total_relation_size('<table>')) AS total_size,
    reltuples::bigint AS estimated_rows
FROM pg_class WHERE relname = '<table>';

-- Check constraints
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = '<table>'::regclass AND contype = 'c';

-- Triggers on this table
SELECT tgname, pg_get_triggerdef(oid)
FROM pg_trigger
WHERE tgrelid = '<table>'::regclass AND NOT tgisinternal;

-- Partitioning info (if partitioned)
SELECT
    inhrelid::regclass AS partition_name,
    pg_get_expr(relpartbound, inhrelid) AS partition_bound
FROM pg_inherits
JOIN pg_class ON pg_class.oid = inhrelid
WHERE inhparent = '<table>'::regclass;
```

### MySQL

```sql
-- Full table definition (structure, indexes, FKs, engine, charset)
SHOW CREATE TABLE <table>;

-- Column details
DESCRIBE <table>;

-- All indexes
SHOW INDEX FROM <table>;

-- Table stats
SELECT table_rows, data_length, index_length,
       ROUND((data_length + index_length) / 1024 / 1024, 2) AS total_mb
FROM information_schema.tables
WHERE table_schema = DATABASE() AND table_name = '<table>';

-- Foreign keys (outgoing)
SELECT constraint_name, column_name, referenced_table_name, referenced_column_name
FROM information_schema.key_column_usage
WHERE table_schema = DATABASE() AND table_name = '<table>'
  AND referenced_table_name IS NOT NULL;

-- Foreign keys (incoming)
SELECT constraint_name, table_name, column_name
FROM information_schema.key_column_usage
WHERE table_schema = DATABASE() AND referenced_table_name = '<table>';

-- Triggers
SHOW TRIGGERS WHERE `Table` = '<table>';
```

## Index Health

### PostgreSQL

```sql
-- Index usage stats
SELECT
    indexrelname AS index_name,
    idx_scan AS times_used,
    idx_tup_read,
    idx_tup_fetch,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_stat_user_indexes
WHERE relname = '<table>'
ORDER BY idx_scan ASC;

-- Sequential scan pressure
SELECT
    seq_scan,
    seq_tup_read,
    idx_scan,
    CASE WHEN seq_scan > 0
         THEN seq_tup_read / seq_scan
         ELSE 0 END AS avg_rows_per_seq_scan
FROM pg_stat_user_tables
WHERE relname = '<table>';

-- Duplicate or overlapping indexes (heuristic only — review predicates,
-- sort order, INCLUDE columns, and expressions before treating as waste)
SELECT
    a.indexrelid::regclass AS index_a,
    b.indexrelid::regclass AS index_b,
    pg_size_pretty(pg_relation_size(a.indexrelid)) AS size_a
FROM pg_index a
JOIN pg_index b ON a.indrelid = b.indrelid
  AND a.indexrelid != b.indexrelid
  AND a.indkey::text LIKE b.indkey::text || '%'
WHERE a.indrelid = '<table>'::regclass;

-- Invalid indexes (from failed CONCURRENTLY operations)
SELECT indexrelid::regclass AS index_name
FROM pg_index
WHERE indrelid = '<table>'::regclass AND NOT indisvalid;
```

### MySQL

```sql
-- Index cardinality (selectivity indicator)
SHOW INDEX FROM <table>;
-- Look at Cardinality column: higher = more selective = more useful

-- Index usage (MySQL 8.0+ with performance_schema)
SELECT
    object_name AS table_name,
    index_name,
    count_read,
    count_write
FROM performance_schema.table_io_waits_summary_by_index_usage
WHERE object_schema = DATABASE() AND object_name = '<table>'
ORDER BY count_read ASC;
```

## Write Pressure Analysis

### PostgreSQL

```sql
-- Write activity on target table
SELECT
    n_tup_ins AS inserts,
    n_tup_upd AS updates,
    n_tup_del AS deletes,
    n_tup_ins + n_tup_upd + n_tup_del AS total_writes,
    n_tup_hot_upd AS hot_updates,
    CASE WHEN n_tup_upd > 0
         THEN ROUND(100.0 * n_tup_hot_upd / n_tup_upd, 1)
         ELSE 0 END AS hot_update_pct
FROM pg_stat_user_tables
WHERE relname = '<table>';
```

### MySQL

```sql
-- Table handler stats (session-level, run before and after a workload sample)
SHOW SESSION STATUS LIKE 'Handler_write';
SHOW SESSION STATUS LIKE 'Handler_update';
SHOW SESSION STATUS LIKE 'Handler_delete';
```

## Co-Resident Query Detection

### PostgreSQL (requires pg_stat_statements)

```sql
-- Top queries touching this table by total time
SELECT
    queryid,
    LEFT(query, 120) AS query_preview,
    calls,
    ROUND(mean_exec_time::numeric, 2) AS mean_ms,
    ROUND(total_exec_time::numeric, 2) AS total_ms,
    rows
FROM pg_stat_statements
WHERE query ILIKE '%<table>%'
ORDER BY total_exec_time DESC
LIMIT 20;

-- Write-heavy queries on this table
SELECT
    queryid,
    LEFT(query, 120) AS query_preview,
    calls,
    ROUND(mean_exec_time::numeric, 2) AS mean_ms
FROM pg_stat_statements
WHERE query ILIKE '%<table>%'
  AND (query ILIKE 'INSERT%' OR query ILIKE 'UPDATE%' OR query ILIKE 'DELETE%')
ORDER BY calls DESC
LIMIT 10;
```

## Table Bloat Estimation

### PostgreSQL

```sql
-- Dead tuple ratio (indicates need for VACUUM)
SELECT
    relname,
    n_live_tup,
    n_dead_tup,
    CASE WHEN n_live_tup > 0
         THEN ROUND(100.0 * n_dead_tup / n_live_tup, 1)
         ELSE 0 END AS dead_pct,
    last_vacuum,
    last_autovacuum,
    last_analyze,
    last_autoanalyze
FROM pg_stat_user_tables
WHERE relname = '<table>';
```

## Statistics Freshness

### PostgreSQL

```sql
-- When were stats last updated?
SELECT
    relname,
    last_analyze,
    last_autoanalyze,
    n_mod_since_analyze
FROM pg_stat_user_tables
WHERE relname = '<table>';
-- If n_mod_since_analyze is high relative to row count, stats may be stale
```

### MySQL

```sql
-- Table stats update time
SELECT table_name, update_time
FROM information_schema.tables
WHERE table_schema = DATABASE() AND table_name = '<table>';

-- ⚠ ANALYZE TABLE is NOT L0 — it updates optimizer statistics and acquires metadata locks.
-- Do NOT include in copy-paste discovery blocks. Treat as a separate L1 maintenance action
-- that requires explicit user acknowledgement before execution.
-- ANALYZE TABLE <table>;
```
