-- =============================================================================
-- MariaDB Health Check (L0 — read-only, environment-dependent coverage)
-- =============================================================================
-- Produces a structured diagnostic snapshot of database health.
-- Run as a monitoring/read-only role. No writes, no locks, no side effects.
-- Requires MariaDB 10.5+ for best metadata coverage.
-- Several sections depend on performance_schema, information_schema userstat
-- tables, and InnoDB metadata visibility, so reduced-privilege roles may see
-- partial results.
--
-- Sections:
--   1. Engine Info
--   2. Database Size & Connections
--   3. Table Sizes & Engine Distribution
--   4. Buffer Pool Performance (InnoDB)
--   5. Temp Table & Sort Activity
--   6. Table Maintenance Status
--   7. Long-Running Queries & Lock Contention
--   8. Replication Status (if applicable)
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. ENGINE INFO
-- ---------------------------------------------------------------------------
SELECT
    'engine_info' AS section,
    @@version AS mariadb_version,
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
    (SELECT VARIABLE_VALUE
     FROM information_schema.GLOBAL_STATUS
     WHERE VARIABLE_NAME = 'THREADS_CONNECTED') AS current_connections,
    (SELECT VARIABLE_VALUE
     FROM information_schema.GLOBAL_STATUS
     WHERE VARIABLE_NAME = 'MAX_USED_CONNECTIONS') AS max_used_connections,
    @@max_connections AS max_allowed,
    ROUND(100.0 * (
        SELECT VARIABLE_VALUE
        FROM information_schema.GLOBAL_STATUS
        WHERE VARIABLE_NAME = 'THREADS_CONNECTED'
    ) / @@max_connections, 1) AS usage_pct,
    (SELECT VARIABLE_VALUE
     FROM information_schema.GLOBAL_STATUS
     WHERE VARIABLE_NAME = 'ABORTED_CONNECTS') AS aborted_connects;

-- ---------------------------------------------------------------------------
-- 3. TABLE SIZES & ENGINE DISTRIBUTION
-- ---------------------------------------------------------------------------
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
  AND data_free > 1048576
  AND data_length > 0
  AND (100.0 * data_free / data_length) > 20
ORDER BY data_free DESC;

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
    (SELECT VARIABLE_VALUE
     FROM information_schema.GLOBAL_STATUS
     WHERE VARIABLE_NAME = 'INNODB_BUFFER_POOL_READ_REQUESTS') AS logical_reads,
    (SELECT VARIABLE_VALUE
     FROM information_schema.GLOBAL_STATUS
     WHERE VARIABLE_NAME = 'INNODB_BUFFER_POOL_READS') AS disk_reads,
    ROUND(100.0 * (1 - (
        (SELECT VARIABLE_VALUE
         FROM information_schema.GLOBAL_STATUS
         WHERE VARIABLE_NAME = 'INNODB_BUFFER_POOL_READS') /
        GREATEST((
            SELECT VARIABLE_VALUE
            FROM information_schema.GLOBAL_STATUS
            WHERE VARIABLE_NAME = 'INNODB_BUFFER_POOL_READ_REQUESTS'
        ), 1)
    )), 2) AS hit_ratio_pct,
    @@innodb_buffer_pool_size / 1024 / 1024 AS buffer_pool_mb;

-- ---------------------------------------------------------------------------
-- 5. TEMP TABLE & SORT ACTIVITY
-- ---------------------------------------------------------------------------
SELECT
    'temp_table_activity' AS section,
    (SELECT VARIABLE_VALUE
     FROM information_schema.GLOBAL_STATUS
     WHERE VARIABLE_NAME = 'CREATED_TMP_TABLES') AS tmp_tables_created,
    (SELECT VARIABLE_VALUE
     FROM information_schema.GLOBAL_STATUS
     WHERE VARIABLE_NAME = 'CREATED_TMP_DISK_TABLES') AS tmp_disk_tables,
    ROUND(100.0 * (
        SELECT VARIABLE_VALUE
        FROM information_schema.GLOBAL_STATUS
        WHERE VARIABLE_NAME = 'CREATED_TMP_DISK_TABLES'
    ) / GREATEST((
        SELECT VARIABLE_VALUE
        FROM information_schema.GLOBAL_STATUS
        WHERE VARIABLE_NAME = 'CREATED_TMP_TABLES'
    ), 1), 1) AS disk_tmp_pct,
    (SELECT VARIABLE_VALUE
     FROM information_schema.GLOBAL_STATUS
     WHERE VARIABLE_NAME = 'SORT_MERGE_PASSES') AS sort_merge_passes;

SELECT
    'handler_stats' AS section,
    (SELECT VARIABLE_VALUE
     FROM information_schema.GLOBAL_STATUS
     WHERE VARIABLE_NAME = 'HANDLER_READ_FIRST') AS full_index_scans,
    (SELECT VARIABLE_VALUE
     FROM information_schema.GLOBAL_STATUS
     WHERE VARIABLE_NAME = 'HANDLER_READ_RND_NEXT') AS full_table_scan_rows,
    (SELECT VARIABLE_VALUE
     FROM information_schema.GLOBAL_STATUS
     WHERE VARIABLE_NAME = 'HANDLER_READ_KEY') AS index_lookups,
    (SELECT VARIABLE_VALUE
     FROM information_schema.GLOBAL_STATUS
     WHERE VARIABLE_NAME = 'HANDLER_READ_NEXT') AS index_range_rows;

-- ---------------------------------------------------------------------------
-- 6. TABLE MAINTENANCE STATUS
-- ---------------------------------------------------------------------------
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
FROM information_schema.PROCESSLIST
WHERE command != 'Sleep'
  AND time > 30
  AND db = DATABASE()
ORDER BY time DESC;

SELECT
    'lock_waits' AS section,
    w.requesting_trx_id AS waiting_trx_id,
    r.trx_mysql_thread_id AS waiting_thread,
    LEFT(r.trx_query, 150) AS waiting_query,
    w.blocking_trx_id AS blocking_trx_id,
    b.trx_mysql_thread_id AS blocking_thread,
    LEFT(b.trx_query, 150) AS blocking_query,
    TIMESTAMPDIFF(SECOND, r.trx_wait_started, NOW()) AS wait_seconds
FROM information_schema.INNODB_LOCK_WAITS w
JOIN information_schema.INNODB_TRX r
    ON r.trx_id = w.requesting_trx_id
JOIN information_schema.INNODB_TRX b
    ON b.trx_id = w.blocking_trx_id
ORDER BY wait_seconds DESC;

-- ---------------------------------------------------------------------------
-- 8. REPLICATION STATUS (if applicable)
-- ---------------------------------------------------------------------------
SELECT
    'replication_status_note' AS section,
    'Run SHOW REPLICA STATUS or SHOW SLAVE STATUS separately if this server is a replica.' AS note;
