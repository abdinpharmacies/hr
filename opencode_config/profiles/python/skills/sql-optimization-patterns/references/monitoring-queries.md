# Monitoring Queries

Templates for periodic performance reviews (Phase Routing: periodic review) and ongoing health checks. These feed into Phase 2 batch diagnosis and Phase 5 review delivery.

## Top Queries by Impact

### PostgreSQL (requires pg_stat_statements extension)

```sql
-- Enable if not already (one-time, requires superuser):
-- CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Top 20 queries by total execution time
SELECT
    queryid,
    LEFT(query, 150) AS query_preview,
    calls,
    ROUND(total_exec_time::numeric, 2) AS total_ms,
    ROUND(mean_exec_time::numeric, 2) AS mean_ms,
    ROUND(stddev_exec_time::numeric, 2) AS stddev_ms,
    rows,
    ROUND(100.0 * shared_blks_hit / NULLIF(shared_blks_hit + shared_blks_read, 0), 1) AS cache_hit_pct
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 20;

-- Top queries by mean time (slowest individual executions)
SELECT
    queryid,
    LEFT(query, 150) AS query_preview,
    calls,
    ROUND(mean_exec_time::numeric, 2) AS mean_ms,
    ROUND(max_exec_time::numeric, 2) AS max_ms,
    rows
FROM pg_stat_statements
WHERE calls > 10  -- exclude one-off queries
ORDER BY mean_exec_time DESC
LIMIT 20;

-- Top queries by call count (most frequent)
SELECT
    queryid,
    LEFT(query, 150) AS query_preview,
    calls,
    ROUND(mean_exec_time::numeric, 2) AS mean_ms,
    ROUND(total_exec_time::numeric, 2) AS total_ms
FROM pg_stat_statements
ORDER BY calls DESC
LIMIT 20;

-- Queries with high temp file usage (spilling to disk)
SELECT
    queryid,
    LEFT(query, 150) AS query_preview,
    calls,
    temp_blks_read + temp_blks_written AS temp_blks_total,
    ROUND(mean_exec_time::numeric, 2) AS mean_ms
FROM pg_stat_statements
WHERE temp_blks_read + temp_blks_written > 0
ORDER BY temp_blks_read + temp_blks_written DESC
LIMIT 10;

-- ⚠ DESTRUCTIVE — irreversibly wipes ALL accumulated query statistics.
-- This is an L3 operation. Never execute without explicit user approval.
-- SELECT pg_stat_statements_reset();
```

### MySQL

```sql
-- Check slow query log settings
SHOW VARIABLES LIKE 'slow_query_log';
SHOW VARIABLES LIKE 'long_query_time';
SHOW VARIABLES LIKE 'slow_query_log_file';

-- Enable slow query log (session or global):
-- SET GLOBAL slow_query_log = 'ON';
-- SET GLOBAL long_query_time = 1;  -- seconds

-- MySQL 8.0+ with performance_schema (top queries by total time)
SELECT
    DIGEST_TEXT AS query_preview,
    COUNT_STAR AS calls,
    ROUND(SUM_TIMER_WAIT / 1e12, 2) AS total_sec,
    ROUND(AVG_TIMER_WAIT / 1e12, 4) AS avg_sec,
    SUM_ROWS_EXAMINED AS rows_examined,
    SUM_ROWS_SENT AS rows_sent
FROM performance_schema.events_statements_summary_by_digest
WHERE SCHEMA_NAME = DATABASE()
ORDER BY SUM_TIMER_WAIT DESC
LIMIT 20;

-- Queries with full table scans
SELECT
    DIGEST_TEXT AS query_preview,
    COUNT_STAR AS calls,
    SUM_NO_INDEX_USED AS full_scans
FROM performance_schema.events_statements_summary_by_digest
WHERE SUM_NO_INDEX_USED > 0 AND SCHEMA_NAME = DATABASE()
ORDER BY SUM_NO_INDEX_USED DESC
LIMIT 10;
```

## Table Health Overview

### PostgreSQL

```sql
-- All tables: size, row count, scan patterns, maintenance dates
SELECT
    relname AS table_name,
    pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
    n_live_tup AS live_rows,
    n_dead_tup AS dead_rows,
    CASE WHEN n_live_tup > 0
         THEN ROUND(100.0 * n_dead_tup / n_live_tup, 1)
         ELSE 0 END AS dead_pct,
    seq_scan,
    idx_scan,
    CASE WHEN seq_scan + idx_scan > 0
         THEN ROUND(100.0 * idx_scan / (seq_scan + idx_scan), 1)
         ELSE 0 END AS idx_scan_pct,
    last_autovacuum,
    last_autoanalyze
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(relid) DESC;
```

### MySQL

```sql
-- All tables: size, rows, engine
SELECT
    table_name,
    engine,
    table_rows,
    ROUND(data_length / 1024 / 1024, 2) AS data_mb,
    ROUND(index_length / 1024 / 1024, 2) AS index_mb,
    ROUND((data_length + index_length) / 1024 / 1024, 2) AS total_mb
FROM information_schema.tables
WHERE table_schema = DATABASE()
ORDER BY data_length + index_length DESC;
```

## Unused & Redundant Indexes

### PostgreSQL

```sql
-- Indexes never used (candidates for removal)
SELECT
    schemaname,
    relname AS table_name,
    indexrelname AS index_name,
    idx_scan AS times_used,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_stat_user_indexes
WHERE idx_scan = 0
ORDER BY pg_relation_size(indexrelid) DESC;

-- Total wasted space from unused indexes
SELECT
    pg_size_pretty(SUM(pg_relation_size(indexrelid))) AS total_unused_index_size
FROM pg_stat_user_indexes
WHERE idx_scan = 0;
```

### MySQL (8.0+ with performance_schema)

```sql
-- Indexes with zero reads
SELECT
    object_schema,
    object_name AS table_name,
    index_name,
    count_read,
    count_write
FROM performance_schema.table_io_waits_summary_by_index_usage
WHERE object_schema = DATABASE()
  AND index_name IS NOT NULL
  AND count_read = 0
ORDER BY count_write DESC;
```

## Active Session Analysis

### PostgreSQL

```sql
-- Currently running queries (check for long-runners before DDL)
SELECT
    pid,
    now() - query_start AS duration,
    state,
    wait_event_type,
    wait_event,
    LEFT(query, 100) AS query_preview
FROM pg_stat_activity
WHERE state != 'idle'
  AND pid != pg_backend_pid()
ORDER BY query_start ASC;

-- Blocked queries (lock contention)
SELECT
    blocked.pid AS blocked_pid,
    blocked.query AS blocked_query,
    blocking.pid AS blocking_pid,
    blocking.query AS blocking_query
FROM pg_stat_activity blocked
JOIN pg_locks bl ON bl.pid = blocked.pid AND NOT bl.granted
JOIN pg_locks gl ON gl.locktype = bl.locktype
    AND gl.database IS NOT DISTINCT FROM bl.database
    AND gl.relation IS NOT DISTINCT FROM bl.relation
    AND gl.page IS NOT DISTINCT FROM bl.page
    AND gl.tuple IS NOT DISTINCT FROM bl.tuple
    AND gl.pid != bl.pid
    AND gl.granted
JOIN pg_stat_activity blocking ON blocking.pid = gl.pid;
```

### MySQL

```sql
-- Currently running queries
SHOW FULL PROCESSLIST;

-- Long-running queries (> 5 seconds)
SELECT id, user, host, db, command, time, state, LEFT(info, 100) AS query_preview
FROM information_schema.processlist
WHERE command != 'Sleep' AND time > 5
ORDER BY time DESC;

-- Lock waits (InnoDB)
SELECT * FROM information_schema.innodb_lock_waits;
```

## Cache & Buffer Efficiency

### PostgreSQL

```sql
-- Overall cache hit ratio (should be >99% for OLTP)
SELECT
    ROUND(100.0 * sum(blks_hit) / NULLIF(sum(blks_hit) + sum(blks_read), 0), 2) AS cache_hit_pct
FROM pg_stat_database;

-- Per-table cache hit ratio
SELECT
    relname,
    ROUND(100.0 * heap_blks_hit / NULLIF(heap_blks_hit + heap_blks_read, 0), 2) AS table_cache_hit_pct,
    ROUND(100.0 * idx_blks_hit / NULLIF(idx_blks_hit + idx_blks_read, 0), 2) AS index_cache_hit_pct
FROM pg_statio_user_tables
WHERE heap_blks_hit + heap_blks_read > 0
ORDER BY heap_blks_read DESC
LIMIT 10;
```

### MySQL

```sql
-- InnoDB buffer pool hit ratio
SHOW GLOBAL STATUS LIKE 'Innodb_buffer_pool_read_requests';  -- logical reads
SHOW GLOBAL STATUS LIKE 'Innodb_buffer_pool_reads';          -- disk reads
-- Hit ratio = 1 - (reads / read_requests). Should be >99%

-- Buffer pool usage
SHOW GLOBAL STATUS LIKE 'Innodb_buffer_pool_pages%';
```

## Connection Health

### PostgreSQL

```sql
-- Connection count by state
SELECT state, COUNT(*)
FROM pg_stat_activity
GROUP BY state;

-- Connection limit
SHOW max_connections;
```

### MySQL

```sql
SHOW GLOBAL STATUS LIKE 'Threads_connected';
SHOW GLOBAL STATUS LIKE 'Max_used_connections';
SHOW VARIABLES LIKE 'max_connections';
```
