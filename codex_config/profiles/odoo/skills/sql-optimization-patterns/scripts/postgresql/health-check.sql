-- =============================================================================
-- PostgreSQL Health Check (L0 — read-only, safe to run anywhere)
-- =============================================================================
-- Produces a structured diagnostic snapshot of database health.
-- Run as a monitoring/read-only role. No writes, no locks, no side effects.
--
-- Sections:
--   1. Engine Info
--   2. Database Size & Connections
--   3. Table Sizes & Bloat
--   4. Cache Performance
--   5. Statistics Freshness
--   6. Vacuum & Maintenance Status
--   7. Temp File & Sort Spill Activity
--   8. Replication Status (if applicable)
--   9. Long-Running Queries & Lock Contention
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. ENGINE INFO
-- ---------------------------------------------------------------------------
SELECT
    'engine_info' AS section,
    version() AS pg_version,
    current_database() AS current_db,
    current_user AS connected_as,
    inet_server_addr() AS server_addr,
    inet_server_port() AS server_port,
    pg_postmaster_start_time() AS server_started,
    NOW() - pg_postmaster_start_time() AS uptime;

-- ---------------------------------------------------------------------------
-- 2. DATABASE SIZE & CONNECTIONS
-- ---------------------------------------------------------------------------
SELECT
    'database_size' AS section,
    datname,
    pg_size_pretty(pg_database_size(datname)) AS size,
    numbackends AS active_connections
FROM pg_stat_database
WHERE datname = current_database();

SELECT
    'connection_usage' AS section,
    COUNT(*) AS total_connections,
    COUNT(*) FILTER (WHERE state = 'active') AS active,
    COUNT(*) FILTER (WHERE state = 'idle') AS idle,
    COUNT(*) FILTER (WHERE state = 'idle in transaction') AS idle_in_tx,
    COUNT(*) FILTER (WHERE state = 'idle in transaction (aborted)') AS idle_in_tx_aborted,
    (SELECT setting::int FROM pg_settings WHERE name = 'max_connections') AS max_connections,
    ROUND(100.0 * COUNT(*) / (SELECT setting::int FROM pg_settings WHERE name = 'max_connections'), 1) AS usage_pct
FROM pg_stat_activity
WHERE datname = current_database();

-- ---------------------------------------------------------------------------
-- 3. TABLE SIZES & BLOAT INDICATORS
-- ---------------------------------------------------------------------------
-- Top 20 tables by total size (table + indexes)
SELECT
    'table_sizes' AS section,
    schemaname,
    relname AS table_name,
    pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
    pg_size_pretty(pg_relation_size(relid)) AS table_size,
    pg_size_pretty(pg_indexes_size(relid)) AS indexes_size,
    n_live_tup AS live_rows,
    n_dead_tup AS dead_rows,
    CASE WHEN n_live_tup > 0
         THEN ROUND(100.0 * n_dead_tup / n_live_tup, 1)
         ELSE 0 END AS dead_row_pct
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 20;

-- Tables with high dead row ratio (>10% — may need VACUUM)
SELECT
    'bloat_candidates' AS section,
    schemaname,
    relname AS table_name,
    n_live_tup AS live_rows,
    n_dead_tup AS dead_rows,
    ROUND(100.0 * n_dead_tup / GREATEST(n_live_tup, 1), 1) AS dead_row_pct,
    last_vacuum,
    last_autovacuum
FROM pg_stat_user_tables
WHERE n_dead_tup > 1000
  AND (n_live_tup = 0 OR (100.0 * n_dead_tup / n_live_tup) > 10)
ORDER BY n_dead_tup DESC;

-- ---------------------------------------------------------------------------
-- 4. CACHE PERFORMANCE
-- ---------------------------------------------------------------------------
-- Overall cache hit ratio (should be >99% for OLTP workloads)
SELECT
    'cache_overall' AS section,
    SUM(blks_hit) AS blocks_hit,
    SUM(blks_read) AS blocks_read,
    CASE WHEN SUM(blks_hit) + SUM(blks_read) > 0
         THEN ROUND(100.0 * SUM(blks_hit) / (SUM(blks_hit) + SUM(blks_read)), 2)
         ELSE 0 END AS cache_hit_pct
FROM pg_stat_database
WHERE datname = current_database();

-- Per-table cache hit ratio (top 10 worst performers with significant activity)
SELECT
    'cache_per_table' AS section,
    relname AS table_name,
    heap_blks_hit + heap_blks_read AS total_blocks,
    CASE WHEN heap_blks_hit + heap_blks_read > 0
         THEN ROUND(100.0 * heap_blks_hit / (heap_blks_hit + heap_blks_read), 2)
         ELSE 100 END AS table_cache_hit_pct,
    CASE WHEN idx_blks_hit + idx_blks_read > 0
         THEN ROUND(100.0 * idx_blks_hit / (idx_blks_hit + idx_blks_read), 2)
         ELSE 100 END AS index_cache_hit_pct
FROM pg_statio_user_tables
WHERE heap_blks_hit + heap_blks_read > 100
ORDER BY (CASE WHEN heap_blks_hit + heap_blks_read > 0
               THEN 100.0 * heap_blks_hit / (heap_blks_hit + heap_blks_read)
               ELSE 100 END) ASC
LIMIT 10;

-- ---------------------------------------------------------------------------
-- 5. STATISTICS FRESHNESS
-- ---------------------------------------------------------------------------
-- Tables where stats may be stale (high modifications since last analyze)
SELECT
    'stale_stats' AS section,
    schemaname,
    relname AS table_name,
    n_live_tup AS live_rows,
    n_mod_since_analyze AS mods_since_analyze,
    CASE WHEN n_live_tup > 0
         THEN ROUND(100.0 * n_mod_since_analyze / n_live_tup, 1)
         ELSE 0 END AS mod_pct_since_analyze,
    last_analyze,
    last_autoanalyze
FROM pg_stat_user_tables
WHERE n_mod_since_analyze > 1000
  AND (n_live_tup = 0 OR (100.0 * n_mod_since_analyze / n_live_tup) > 20)
ORDER BY n_mod_since_analyze DESC;

-- ---------------------------------------------------------------------------
-- 6. VACUUM & MAINTENANCE STATUS
-- ---------------------------------------------------------------------------
-- Tables approaching or past autovacuum thresholds
SELECT
    'vacuum_status' AS section,
    schemaname,
    relname AS table_name,
    n_dead_tup,
    last_vacuum,
    last_autovacuum,
    last_analyze,
    last_autoanalyze,
    -- Default autovacuum threshold: 50 + 0.2 * n_live_tup
    (50 + 0.2 * n_live_tup)::bigint AS autovacuum_threshold,
    CASE WHEN n_dead_tup > (50 + 0.2 * n_live_tup)
         THEN 'OVERDUE' ELSE 'OK' END AS vacuum_status
FROM pg_stat_user_tables
WHERE n_dead_tup > 0
ORDER BY n_dead_tup DESC
LIMIT 15;

-- ---------------------------------------------------------------------------
-- 7. TEMP FILE & SORT SPILL ACTIVITY
-- ---------------------------------------------------------------------------
-- Database-level temp file usage
SELECT
    'temp_files' AS section,
    datname,
    temp_files AS temp_file_count,
    pg_size_pretty(temp_bytes) AS temp_bytes_total
FROM pg_stat_database
WHERE datname = current_database()
  AND temp_files > 0;

-- ---------------------------------------------------------------------------
-- 8. REPLICATION STATUS (if applicable)
-- ---------------------------------------------------------------------------
SELECT
    'replication' AS section,
    client_addr,
    state,
    sent_lsn,
    write_lsn,
    flush_lsn,
    replay_lsn,
    pg_wal_lsn_diff(sent_lsn, replay_lsn) AS replay_lag_bytes,
    pg_size_pretty(pg_wal_lsn_diff(sent_lsn, replay_lsn)) AS replay_lag_pretty
FROM pg_stat_replication;

-- ---------------------------------------------------------------------------
-- 9. LONG-RUNNING QUERIES & LOCK CONTENTION
-- ---------------------------------------------------------------------------
-- Queries running > 30 seconds
SELECT
    'long_running_queries' AS section,
    pid,
    NOW() - query_start AS duration,
    state,
    wait_event_type,
    wait_event,
    LEFT(query, 200) AS query_preview
FROM pg_stat_activity
WHERE state = 'active'
  AND query_start < NOW() - INTERVAL '30 seconds'
  AND pid != pg_backend_pid()
ORDER BY query_start ASC;

-- Idle transactions (holding locks without doing work)
SELECT
    'idle_transactions' AS section,
    pid,
    NOW() - state_change AS idle_duration,
    LEFT(query, 200) AS last_query
FROM pg_stat_activity
WHERE state = 'idle in transaction'
  AND state_change < NOW() - INTERVAL '1 minute'
ORDER BY state_change ASC;

-- Blocked queries
SELECT
    'blocked_queries' AS section,
    blocked.pid AS blocked_pid,
    NOW() - blocked.query_start AS blocked_duration,
    LEFT(blocked.query, 150) AS blocked_query,
    blocking.pid AS blocking_pid,
    blocking.state AS blocking_state,
    LEFT(blocking.query, 150) AS blocking_query
FROM pg_stat_activity blocked
JOIN pg_locks bl ON bl.pid = blocked.pid AND NOT bl.granted
JOIN pg_locks gl ON gl.locktype = bl.locktype
    AND gl.database IS NOT DISTINCT FROM bl.database
    AND gl.relation IS NOT DISTINCT FROM bl.relation
    AND gl.page IS NOT DISTINCT FROM bl.page
    AND gl.tuple IS NOT DISTINCT FROM bl.tuple
    AND gl.pid != bl.pid
    AND gl.granted
JOIN pg_stat_activity blocking ON blocking.pid = gl.pid
WHERE blocked.pid != pg_backend_pid();
