-- =============================================================================
-- MySQL Health Check (L0 — read-only, environment-dependent coverage)
-- =============================================================================
-- Produces a structured diagnostic snapshot of database health.
-- Run as a monitoring/read-only role. No writes, no locks, no side effects.
-- Requires MySQL 8.0+ for some features; MariaDB equivalents noted where different.
-- Several sections depend on performance_schema and InnoDB metadata visibility,
-- so reduced-privilege roles may see partial results.
--
-- Sections:
--   1. Engine Info
--   2. Database Size & Connections
--   3. Table Sizes & Engine Distribution
--   4. Buffer Pool Performance (InnoDB)
--   5. Query Cache / Temp Table Activity
--   6. Table Maintenance Status
--   7. Long-Running Queries & Lock Contention
--   8. Replication Status (if applicable)
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. ENGINE INFO
-- ---------------------------------------------------------------------------
SELECT
    'engine_info' AS section,
    @@version AS mysql_version,
    @@version_comment AS version_comment,
    DATABASE() AS current_db,
    CURRENT_USER() AS connected_as,
    @@hostname AS server_hostname,
    @@port AS server_port,
    @@datadir AS data_directory;

-- ---------------------------------------------------------------------------
-- 2. DATABASE SIZE & CONNECTIONS
-- ---------------------------------------------------------------------------
SELECT
    'database_size' AS section,
    table_schema AS database_name,
    ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS total_mb,
    ROUND(SUM(data_length) / 1024 / 1024, 2) AS data_mb,
    ROUND(SUM(index_length) / 1024 / 1024, 2) AS index_mb,
    COUNT(*) AS table_count
FROM information_schema.tables
WHERE table_schema = DATABASE()
GROUP BY table_schema;

SELECT
    'connection_status' AS section,
    (SELECT VARIABLE_VALUE FROM performance_schema.global_status
     WHERE VARIABLE_NAME = 'Threads_connected') AS current_connections,
    (SELECT VARIABLE_VALUE FROM performance_schema.global_status
     WHERE VARIABLE_NAME = 'Max_used_connections') AS max_used_connections,
    @@max_connections AS max_allowed,
    ROUND(100.0 * (SELECT VARIABLE_VALUE FROM performance_schema.global_status
     WHERE VARIABLE_NAME = 'Threads_connected') / @@max_connections, 1) AS usage_pct,
    (SELECT VARIABLE_VALUE FROM performance_schema.global_status
     WHERE VARIABLE_NAME = 'Aborted_connects') AS aborted_connects;

-- ---------------------------------------------------------------------------
-- 3. TABLE SIZES & ENGINE DISTRIBUTION
-- ---------------------------------------------------------------------------
-- Top 20 tables by size
SELECT
    'table_sizes' AS section,
    table_name,
    engine,
    table_rows AS estimated_rows,
    ROUND(data_length / 1024 / 1024, 2) AS data_mb,
    ROUND(index_length / 1024 / 1024, 2) AS index_mb,
    ROUND((data_length + index_length) / 1024 / 1024, 2) AS total_mb,
    ROUND(data_free / 1024 / 1024, 2) AS fragmented_mb,
    CASE WHEN data_length > 0
         THEN ROUND(100.0 * data_free / data_length, 1)
         ELSE 0 END AS frag_pct
FROM information_schema.tables
WHERE table_schema = DATABASE()
  AND table_type = 'BASE TABLE'
ORDER BY (data_length + index_length) DESC
LIMIT 20;

-- Fragmented tables (>20% free space in data file)
SELECT
    'fragmented_tables' AS section,
    table_name,
    engine,
    ROUND(data_length / 1024 / 1024, 2) AS data_mb,
    ROUND(data_free / 1024 / 1024, 2) AS fragmented_mb,
    ROUND(100.0 * data_free / GREATEST(data_length, 1), 1) AS frag_pct
FROM information_schema.tables
WHERE table_schema = DATABASE()
  AND table_type = 'BASE TABLE'
  AND data_free > 1048576          -- >1MB free
  AND data_length > 0
  AND (100.0 * data_free / data_length) > 20
ORDER BY data_free DESC;

-- Engine distribution
SELECT
    'engine_distribution' AS section,
    engine,
    COUNT(*) AS table_count,
    ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS total_mb
FROM information_schema.tables
WHERE table_schema = DATABASE()
  AND table_type = 'BASE TABLE'
GROUP BY engine
ORDER BY total_mb DESC;

-- ---------------------------------------------------------------------------
-- 4. BUFFER POOL PERFORMANCE (InnoDB)
-- ---------------------------------------------------------------------------
SELECT
    'buffer_pool' AS section,
    (SELECT VARIABLE_VALUE FROM performance_schema.global_status
     WHERE VARIABLE_NAME = 'Innodb_buffer_pool_read_requests') AS logical_reads,
    (SELECT VARIABLE_VALUE FROM performance_schema.global_status
     WHERE VARIABLE_NAME = 'Innodb_buffer_pool_reads') AS disk_reads,
    ROUND(100.0 * (1 - (
        (SELECT VARIABLE_VALUE FROM performance_schema.global_status
         WHERE VARIABLE_NAME = 'Innodb_buffer_pool_reads') /
        GREATEST((SELECT VARIABLE_VALUE FROM performance_schema.global_status
         WHERE VARIABLE_NAME = 'Innodb_buffer_pool_read_requests'), 1)
    )), 2) AS hit_ratio_pct,
    @@innodb_buffer_pool_size / 1024 / 1024 AS buffer_pool_mb,
    (SELECT VARIABLE_VALUE FROM performance_schema.global_status
     WHERE VARIABLE_NAME = 'Innodb_buffer_pool_pages_total') AS total_pages,
    (SELECT VARIABLE_VALUE FROM performance_schema.global_status
     WHERE VARIABLE_NAME = 'Innodb_buffer_pool_pages_free') AS free_pages,
    (SELECT VARIABLE_VALUE FROM performance_schema.global_status
     WHERE VARIABLE_NAME = 'Innodb_buffer_pool_pages_dirty') AS dirty_pages;

-- ---------------------------------------------------------------------------
-- 5. TEMP TABLE & SORT ACTIVITY
-- ---------------------------------------------------------------------------
SELECT
    'temp_table_activity' AS section,
    (SELECT VARIABLE_VALUE FROM performance_schema.global_status
     WHERE VARIABLE_NAME = 'Created_tmp_tables') AS tmp_tables_created,
    (SELECT VARIABLE_VALUE FROM performance_schema.global_status
     WHERE VARIABLE_NAME = 'Created_tmp_disk_tables') AS tmp_disk_tables,
    ROUND(100.0 * (SELECT VARIABLE_VALUE FROM performance_schema.global_status
     WHERE VARIABLE_NAME = 'Created_tmp_disk_tables') /
     GREATEST((SELECT VARIABLE_VALUE FROM performance_schema.global_status
     WHERE VARIABLE_NAME = 'Created_tmp_tables'), 1), 1) AS disk_tmp_pct,
    (SELECT VARIABLE_VALUE FROM performance_schema.global_status
     WHERE VARIABLE_NAME = 'Sort_merge_passes') AS sort_merge_passes;
-- High disk_tmp_pct (>25%) = increase tmp_table_size/max_heap_table_size
-- High sort_merge_passes = increase sort_buffer_size

-- Handler statistics (read patterns)
SELECT
    'handler_stats' AS section,
    (SELECT VARIABLE_VALUE FROM performance_schema.global_status
     WHERE VARIABLE_NAME = 'Handler_read_first') AS full_index_scans,
    (SELECT VARIABLE_VALUE FROM performance_schema.global_status
     WHERE VARIABLE_NAME = 'Handler_read_rnd_next') AS full_table_scan_rows,
    (SELECT VARIABLE_VALUE FROM performance_schema.global_status
     WHERE VARIABLE_NAME = 'Handler_read_key') AS index_lookups,
    (SELECT VARIABLE_VALUE FROM performance_schema.global_status
     WHERE VARIABLE_NAME = 'Handler_read_next') AS index_range_rows;

-- ---------------------------------------------------------------------------
-- 6. TABLE MAINTENANCE STATUS
-- ---------------------------------------------------------------------------
-- Tables that haven't been analyzed recently or have stale stats
SELECT
    'table_maintenance' AS section,
    table_name,
    engine,
    table_rows,
    update_time,
    CASE WHEN update_time IS NOT NULL
         THEN TIMESTAMPDIFF(DAY, update_time, NOW())
         ELSE NULL END AS days_since_update,
    check_time,
    CASE WHEN check_time IS NOT NULL
         THEN TIMESTAMPDIFF(DAY, check_time, NOW())
         ELSE NULL END AS days_since_check
FROM information_schema.tables
WHERE table_schema = DATABASE()
  AND table_type = 'BASE TABLE'
ORDER BY update_time ASC
LIMIT 15;

-- ---------------------------------------------------------------------------
-- 7. LONG-RUNNING QUERIES & LOCK CONTENTION
-- ---------------------------------------------------------------------------
-- Queries running > 30 seconds
SELECT
    'long_running_queries' AS section,
    id AS process_id,
    user,
    host,
    db,
    command,
    time AS seconds,
    state,
    LEFT(info, 200) AS query_preview
FROM information_schema.processlist
WHERE command != 'Sleep'
  AND time > 30
  AND db = DATABASE()
ORDER BY time DESC;

-- InnoDB lock waits (MySQL 8.0+)
SELECT
    'lock_waits' AS section,
    r.trx_id AS waiting_trx_id,
    r.trx_mysql_thread_id AS waiting_thread,
    LEFT(r.trx_query, 150) AS waiting_query,
    b.trx_id AS blocking_trx_id,
    b.trx_mysql_thread_id AS blocking_thread,
    LEFT(b.trx_query, 150) AS blocking_query,
    TIMESTAMPDIFF(SECOND, r.trx_wait_started, NOW()) AS wait_seconds
FROM information_schema.innodb_trx r
JOIN performance_schema.data_lock_waits w ON r.trx_id = w.REQUESTING_ENGINE_TRANSACTION_ID
JOIN information_schema.innodb_trx b ON b.trx_id = w.BLOCKING_ENGINE_TRANSACTION_ID
ORDER BY wait_seconds DESC;

-- ---------------------------------------------------------------------------
-- 8. REPLICATION STATUS (if applicable)
-- ---------------------------------------------------------------------------
-- Keep the main script SQL-only and section-labeled. Engine-native replica
-- status commands can be run separately when needed.
SELECT
    'replication_status_note' AS section,
    'Run SHOW REPLICA STATUS separately if this server is a replica. Use SHOW SLAVE STATUS on MySQL < 8.0.22 or MariaDB.' AS note;
