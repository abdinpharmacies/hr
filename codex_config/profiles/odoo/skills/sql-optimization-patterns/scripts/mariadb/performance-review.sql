-- =============================================================================
-- MariaDB Performance Review (L0 — read-only, performance_schema-dependent)
-- =============================================================================
-- Comprehensive performance snapshot for periodic reviews.
-- Requires MariaDB 10.5+ with performance_schema enabled.
-- Query-digest sections reflect recent workload, so reset or sample over a
-- known review window when possible.
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

SELECT
    'table_io' AS section,
    table_name,
    rows_read AS read_ops,
    rows_changed AS write_ops,
    CASE WHEN rows_read > 0
         THEN ROUND(rows_changed / rows_read, 2)
         ELSE rows_changed END AS write_to_read_ratio,
    pages_accessed,
    pages_read_from_disk,
    (SELECT COUNT(DISTINCT index_name)
     FROM information_schema.statistics s
     WHERE s.table_schema = DATABASE() AND s.table_name = ts.table_name) AS index_count
FROM information_schema.TABLE_STATISTICS ts
WHERE table_schema = DATABASE()
ORDER BY rows_read DESC, rows_changed DESC
LIMIT 20;

SELECT
    'slow_query_config' AS section,
    @@slow_query_log AS enabled,
    @@long_query_time AS threshold_sec,
    @@slow_query_log_file AS log_file,
    @@log_slow_filter AS slow_filter,
    (SELECT VARIABLE_VALUE
     FROM information_schema.GLOBAL_STATUS
     WHERE VARIABLE_NAME = 'SLOW_QUERIES') AS slow_query_count;

SELECT
    'config_review' AS section,
    variable_name,
    variable_value,
    CASE
        WHEN variable_name = 'innodb_buffer_pool_size'
        THEN 'Recommend 60-80% of RAM for a dedicated DB server'
        WHEN variable_name = 'innodb_flush_log_at_trx_commit'
        THEN '1=safest, 2=faster with crash-loss risk'
        WHEN variable_name = 'innodb_flush_method'
        THEN 'O_DIRECT often reduces double buffering on Linux'
        WHEN variable_name = 'innodb_io_capacity'
        THEN 'Match to storage IOPS'
        WHEN variable_name = 'join_buffer_size'
        THEN 'Fix missing indexes before increasing this'
        WHEN variable_name = 'sort_buffer_size'
        THEN 'Per-connection; large values can waste memory'
        WHEN variable_name = 'tmp_table_size'
        THEN 'Increase with max_heap_table_size if disk temp tables are high'
        WHEN variable_name = 'max_heap_table_size'
        THEN 'Should be aligned with tmp_table_size'
        WHEN variable_name = 'table_open_cache'
        THEN 'Should fit open-table churn'
        WHEN variable_name = 'thread_cache_size'
        THEN 'Reduce thread creation overhead'
        ELSE ''
    END AS guidance
FROM information_schema.GLOBAL_VARIABLES
WHERE variable_name IN (
    'innodb_buffer_pool_size', 'innodb_buffer_pool_instances',
    'innodb_flush_log_at_trx_commit', 'innodb_flush_method',
    'innodb_io_capacity', 'join_buffer_size', 'sort_buffer_size',
    'read_buffer_size', 'tmp_table_size', 'max_heap_table_size',
    'table_open_cache', 'thread_cache_size', 'max_connections'
)
ORDER BY variable_name;

SELECT
    'innodb_row_ops' AS section,
    (SELECT VARIABLE_VALUE
     FROM information_schema.GLOBAL_STATUS
     WHERE VARIABLE_NAME = 'INNODB_ROWS_READ') AS rows_read,
    (SELECT VARIABLE_VALUE
     FROM information_schema.GLOBAL_STATUS
     WHERE VARIABLE_NAME = 'INNODB_ROWS_INSERTED') AS rows_inserted,
    (SELECT VARIABLE_VALUE
     FROM information_schema.GLOBAL_STATUS
     WHERE VARIABLE_NAME = 'INNODB_ROWS_UPDATED') AS rows_updated,
    (SELECT VARIABLE_VALUE
     FROM information_schema.GLOBAL_STATUS
     WHERE VARIABLE_NAME = 'INNODB_ROWS_DELETED') AS rows_deleted;

SELECT
    'innodb_log_waits' AS section,
    (SELECT VARIABLE_VALUE
     FROM information_schema.GLOBAL_STATUS
     WHERE VARIABLE_NAME = 'INNODB_LOG_WAITS') AS log_waits,
    (SELECT VARIABLE_VALUE
     FROM information_schema.GLOBAL_STATUS
     WHERE VARIABLE_NAME = 'INNODB_LOG_WRITE_REQUESTS') AS log_write_requests,
    CASE WHEN (
        SELECT VARIABLE_VALUE
        FROM information_schema.GLOBAL_STATUS
        WHERE VARIABLE_NAME = 'INNODB_LOG_WAITS'
    ) > 0
         THEN 'REVIEW: redo log may be undersized or saturated'
         ELSE 'ok' END AS recommendation;

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
