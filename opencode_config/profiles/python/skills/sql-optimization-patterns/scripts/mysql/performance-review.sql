-- =============================================================================
-- MySQL Performance Review (L0 — read-only, performance_schema-dependent)
-- =============================================================================
-- Comprehensive performance snapshot for periodic reviews.
-- Requires MySQL 8.0+ with performance_schema enabled.
-- Run as a monitoring/read-only role. Query-digest, I/O, and global status
-- sections depend on performance_schema visibility, so minimal roles may see
-- partial results.
--
-- Sections:
--   1. Top Queries by Total Time
--   2. Top Queries by Mean Time (slowest)
--   3. Top Queries by Call Count (most frequent)
--   4. Queries Causing Full Table Scans
--   5. Queries Creating Temp Tables on Disk
--   6. Table I/O Analysis (read vs write patterns)
--   7. Slow Query Log Status
--   8. Configuration Review (key performance settings)
--   9. InnoDB Engine Status Indicators
--  10. Suggested View Candidates
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. TOP QUERIES BY TOTAL TIME
-- ---------------------------------------------------------------------------
SELECT
    'top_by_total_time' AS section,
    DIGEST AS query_id,
    LEFT(DIGEST_TEXT, 200) AS query_preview,
    COUNT_STAR AS calls,
    ROUND(SUM_TIMER_WAIT / 1e12, 2) AS total_sec,
    ROUND(AVG_TIMER_WAIT / 1e12, 4) AS avg_sec,
    ROUND(MAX_TIMER_WAIT / 1e12, 4) AS max_sec,
    SUM_ROWS_EXAMINED AS rows_examined,
    SUM_ROWS_SENT AS rows_sent,
    ROUND(SUM_ROWS_EXAMINED / GREATEST(SUM_ROWS_SENT, 1), 1) AS examine_to_send_ratio,
    SUM_NO_INDEX_USED AS no_index_used
FROM performance_schema.events_statements_summary_by_digest
WHERE SCHEMA_NAME = DATABASE()
  AND DIGEST_TEXT IS NOT NULL
ORDER BY SUM_TIMER_WAIT DESC
LIMIT 20;

-- ---------------------------------------------------------------------------
-- 2. TOP QUERIES BY MEAN TIME (slowest per execution)
-- ---------------------------------------------------------------------------
SELECT
    'top_by_mean_time' AS section,
    LEFT(DIGEST_TEXT, 200) AS query_preview,
    COUNT_STAR AS calls,
    ROUND(AVG_TIMER_WAIT / 1e12, 4) AS avg_sec,
    ROUND(MAX_TIMER_WAIT / 1e12, 4) AS max_sec,
    SUM_ROWS_EXAMINED AS rows_examined,
    SUM_ROWS_SENT AS rows_sent
FROM performance_schema.events_statements_summary_by_digest
WHERE SCHEMA_NAME = DATABASE()
  AND COUNT_STAR > 5
  AND DIGEST_TEXT IS NOT NULL
ORDER BY AVG_TIMER_WAIT DESC
LIMIT 20;

-- ---------------------------------------------------------------------------
-- 3. TOP QUERIES BY CALL COUNT (most frequent)
-- ---------------------------------------------------------------------------
SELECT
    'top_by_calls' AS section,
    LEFT(DIGEST_TEXT, 200) AS query_preview,
    COUNT_STAR AS calls,
    ROUND(AVG_TIMER_WAIT / 1e12, 4) AS avg_sec,
    ROUND(SUM_TIMER_WAIT / 1e12, 2) AS total_sec,
    SUM_ROWS_SENT AS rows_sent,
    ROUND(SUM_ROWS_SENT / GREATEST(COUNT_STAR, 1), 1) AS avg_rows_per_call
FROM performance_schema.events_statements_summary_by_digest
WHERE SCHEMA_NAME = DATABASE()
  AND DIGEST_TEXT IS NOT NULL
ORDER BY COUNT_STAR DESC
LIMIT 20;

-- ---------------------------------------------------------------------------
-- 4. QUERIES CAUSING FULL TABLE SCANS
-- ---------------------------------------------------------------------------
SELECT
    'full_scan_queries' AS section,
    LEFT(DIGEST_TEXT, 200) AS query_preview,
    COUNT_STAR AS calls,
    SUM_NO_INDEX_USED AS no_index_count,
    SUM_NO_GOOD_INDEX_USED AS bad_index_count,
    SUM_ROWS_EXAMINED AS rows_examined,
    SUM_ROWS_SENT AS rows_sent,
    ROUND(SUM_TIMER_WAIT / 1e12, 2) AS total_sec
FROM performance_schema.events_statements_summary_by_digest
WHERE SCHEMA_NAME = DATABASE()
  AND (SUM_NO_INDEX_USED > 0 OR SUM_NO_GOOD_INDEX_USED > 0)
  AND DIGEST_TEXT IS NOT NULL
ORDER BY SUM_ROWS_EXAMINED DESC
LIMIT 15;

-- ---------------------------------------------------------------------------
-- 5. QUERIES CREATING TEMP TABLES ON DISK
-- ---------------------------------------------------------------------------
SELECT
    'disk_temp_queries' AS section,
    LEFT(DIGEST_TEXT, 200) AS query_preview,
    COUNT_STAR AS calls,
    SUM_CREATED_TMP_TABLES AS tmp_tables,
    SUM_CREATED_TMP_DISK_TABLES AS tmp_disk_tables,
    ROUND(100.0 * SUM_CREATED_TMP_DISK_TABLES /
          GREATEST(SUM_CREATED_TMP_TABLES, 1), 1) AS disk_pct,
    ROUND(SUM_TIMER_WAIT / 1e12, 2) AS total_sec
FROM performance_schema.events_statements_summary_by_digest
WHERE SCHEMA_NAME = DATABASE()
  AND SUM_CREATED_TMP_DISK_TABLES > 0
  AND DIGEST_TEXT IS NOT NULL
ORDER BY SUM_CREATED_TMP_DISK_TABLES DESC
LIMIT 15;

-- ---------------------------------------------------------------------------
-- 6. TABLE I/O ANALYSIS (read vs write patterns)
-- ---------------------------------------------------------------------------
SELECT
    'table_io' AS section,
    object_name AS table_name,
    count_read AS read_ops,
    count_write AS write_ops,
    CASE WHEN count_read > 0
         THEN ROUND(count_write / count_read, 2)
         ELSE count_write END AS write_to_read_ratio,
    ROUND(sum_timer_read / 1e12, 2) AS read_sec,
    ROUND(sum_timer_write / 1e12, 2) AS write_sec,
    count_fetch AS full_scans,
    (SELECT COUNT(DISTINCT index_name)
     FROM information_schema.statistics s
     WHERE s.table_schema = DATABASE() AND s.table_name = t.object_name) AS index_count
FROM performance_schema.table_io_waits_summary_by_table t
WHERE object_schema = DATABASE()
ORDER BY (sum_timer_read + sum_timer_write) DESC
LIMIT 20;

-- ---------------------------------------------------------------------------
-- 7. SLOW QUERY LOG STATUS
-- ---------------------------------------------------------------------------
SELECT
    'slow_query_config' AS section,
    @@slow_query_log AS enabled,
    @@long_query_time AS threshold_sec,
    @@slow_query_log_file AS log_file,
    @@log_queries_not_using_indexes AS log_no_index,
    (SELECT VARIABLE_VALUE FROM performance_schema.global_status
     WHERE VARIABLE_NAME = 'Slow_queries') AS slow_query_count;

-- ---------------------------------------------------------------------------
-- 8. CONFIGURATION REVIEW (key performance settings)
-- ---------------------------------------------------------------------------
SELECT
    'config_review' AS section,
    variable_name,
    variable_value,
    CASE
        WHEN variable_name = 'innodb_buffer_pool_size'
        THEN 'Recommend 70-80% of RAM for dedicated DB server'
        WHEN variable_name = 'innodb_log_file_size'
        THEN 'Larger = better write throughput, longer recovery'
        WHEN variable_name = 'innodb_flush_log_at_trx_commit'
        THEN '1=safe (ACID), 2=faster (risk 1s data loss on crash), 0=fastest (risk data loss)'
        WHEN variable_name = 'innodb_flush_method'
        THEN 'O_DIRECT recommended for Linux to avoid double buffering'
        WHEN variable_name = 'innodb_io_capacity'
        THEN 'Match to storage IOPS: SSD=2000-20000, HDD=200'
        WHEN variable_name = 'innodb_io_capacity_max'
        THEN 'Upper bound for I/O during flushing'
        WHEN variable_name = 'join_buffer_size'
        THEN 'Used for joins without indexes — increasing may help but fix the index first'
        WHEN variable_name = 'sort_buffer_size'
        THEN 'Per-connection; too high wastes memory with many connections'
        WHEN variable_name = 'tmp_table_size'
        THEN 'Max size for in-memory temp tables (with max_heap_table_size)'
        WHEN variable_name = 'max_heap_table_size'
        THEN 'Must match tmp_table_size for effect'
        WHEN variable_name = 'table_open_cache'
        THEN 'Should be > number of tables * max_connections'
        WHEN variable_name = 'thread_cache_size'
        THEN 'Reduce thread creation overhead'
        ELSE ''
    END AS guidance
FROM performance_schema.global_variables
WHERE variable_name IN (
    'innodb_buffer_pool_size', 'innodb_buffer_pool_instances',
    'innodb_log_file_size', 'innodb_flush_log_at_trx_commit',
    'innodb_flush_method', 'innodb_io_capacity', 'innodb_io_capacity_max',
    'join_buffer_size', 'sort_buffer_size', 'read_buffer_size',
    'tmp_table_size', 'max_heap_table_size',
    'table_open_cache', 'thread_cache_size',
    'max_connections', 'innodb_file_per_table'
)
ORDER BY variable_name;

-- ---------------------------------------------------------------------------
-- 9. INNODB ENGINE STATUS INDICATORS
-- ---------------------------------------------------------------------------
-- Row operations
SELECT
    'innodb_row_ops' AS section,
    (SELECT VARIABLE_VALUE FROM performance_schema.global_status
     WHERE VARIABLE_NAME = 'Innodb_rows_read') AS rows_read,
    (SELECT VARIABLE_VALUE FROM performance_schema.global_status
     WHERE VARIABLE_NAME = 'Innodb_rows_inserted') AS rows_inserted,
    (SELECT VARIABLE_VALUE FROM performance_schema.global_status
     WHERE VARIABLE_NAME = 'Innodb_rows_updated') AS rows_updated,
    (SELECT VARIABLE_VALUE FROM performance_schema.global_status
     WHERE VARIABLE_NAME = 'Innodb_rows_deleted') AS rows_deleted;

-- Log waits (should be 0; if not, innodb_log_file_size may be too small)
SELECT
    'innodb_log_waits' AS section,
    (SELECT VARIABLE_VALUE FROM performance_schema.global_status
     WHERE VARIABLE_NAME = 'Innodb_log_waits') AS log_waits,
    (SELECT VARIABLE_VALUE FROM performance_schema.global_status
     WHERE VARIABLE_NAME = 'Innodb_log_writes') AS log_writes,
    CASE WHEN (SELECT VARIABLE_VALUE FROM performance_schema.global_status
               WHERE VARIABLE_NAME = 'Innodb_log_waits') > 0
         THEN 'REVIEW: increase innodb_log_file_size'
         ELSE 'ok' END AS recommendation;

-- ---------------------------------------------------------------------------
-- 10. SUGGESTED VIEW CANDIDATES
-- ---------------------------------------------------------------------------
-- Frequently executed JOIN queries that could be abstracted into views
-- for simplicity, consistency, and access control.
SELECT
    'view_candidates' AS section,
    LEFT(DIGEST_TEXT, 300) AS query_pattern,
    COUNT_STAR AS calls,
    ROUND(AVG_TIMER_WAIT / 1e12, 4) AS avg_sec,
    ROUND(SUM_TIMER_WAIT / 1e12, 2) AS total_sec
FROM performance_schema.events_statements_summary_by_digest
WHERE SCHEMA_NAME = DATABASE()
  AND DIGEST_TEXT LIKE '%JOIN%'
  AND COUNT_STAR > 50
  AND DIGEST_TEXT IS NOT NULL
ORDER BY COUNT_STAR DESC
LIMIT 10;
