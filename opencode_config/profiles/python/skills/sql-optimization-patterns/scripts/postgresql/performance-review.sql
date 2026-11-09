-- =============================================================================
-- PostgreSQL Performance Review (L0 — read-only)
-- =============================================================================
-- Comprehensive performance snapshot for periodic reviews.
-- Query-level sections require pg_stat_statements. If it is unavailable, this
-- script emits a note and continues with table- and configuration-level review.
-- Run as a monitoring/read-only role.
--
-- Sections:
--   1. Query Statistics Availability Note
--   2. Sequential Scan Dominance (tables needing indexes)
--   3. Table Write vs Read Ratio
--   4. Configuration Review (key performance settings)
--   5. Checkpoint & WAL Activity
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. QUERY STATISTICS AVAILABILITY NOTE
-- ---------------------------------------------------------------------------
SELECT
    'query_stats_note' AS section,
    CASE
        WHEN EXISTS (
            SELECT 1
            FROM pg_extension
            WHERE extname = 'pg_stat_statements'
        )
        THEN 'pg_stat_statements is installed. Use references/monitoring-queries.md for query-level review templates.'
        ELSE 'pg_stat_statements is not installed. Query-level review sections are skipped; table and configuration sections below remain valid.'
    END AS note;

-- ---------------------------------------------------------------------------
-- 2. SEQUENTIAL SCAN DOMINANCE
-- ---------------------------------------------------------------------------
-- Tables where sequential scans heavily outweigh index scans.
SELECT
    'seq_scan_dominance' AS section,
    schemaname,
    relname AS table_name,
    seq_scan,
    idx_scan,
    CASE WHEN seq_scan + idx_scan > 0
         THEN ROUND(100.0 * seq_scan / (seq_scan + idx_scan), 1)
         ELSE 0 END AS seq_scan_pct,
    seq_tup_read,
    CASE WHEN seq_scan > 0
         THEN seq_tup_read / seq_scan
         ELSE 0 END AS avg_rows_per_seq_scan,
    n_live_tup AS live_rows,
    pg_size_pretty(pg_relation_size(relid)) AS table_size
FROM pg_stat_user_tables
WHERE seq_scan > 0
  AND n_live_tup > 5000
  AND (idx_scan = 0 OR seq_scan > idx_scan * 5)
ORDER BY seq_tup_read DESC
LIMIT 15;

-- ---------------------------------------------------------------------------
-- 3. TABLE WRITE vs READ RATIO
-- ---------------------------------------------------------------------------
-- Understanding which tables are write-heavy helps assess index overhead impact.
SELECT
    'write_read_ratio' AS section,
    schemaname,
    relname AS table_name,
    seq_tup_read + idx_tup_fetch AS total_reads,
    n_tup_ins + n_tup_upd + n_tup_del AS total_writes,
    CASE WHEN seq_tup_read + idx_tup_fetch > 0
         THEN ROUND(
             (n_tup_ins + n_tup_upd + n_tup_del)::numeric /
             (seq_tup_read + idx_tup_fetch), 3
         )
         ELSE 0 END AS write_to_read_ratio,
    (SELECT COUNT(*) FROM pg_indexes WHERE tablename = relname AND schemaname = t.schemaname) AS index_count
FROM pg_stat_user_tables t
WHERE (seq_tup_read + idx_tup_fetch + n_tup_ins + n_tup_upd + n_tup_del) > 1000
ORDER BY (n_tup_ins + n_tup_upd + n_tup_del) DESC
LIMIT 15;

-- ---------------------------------------------------------------------------
-- 4. CONFIGURATION REVIEW (key performance settings)
-- ---------------------------------------------------------------------------
SELECT
    'config_review' AS section,
    name AS setting_name,
    setting AS current_value,
    unit,
    CASE
        -- shared_buffers: typically 25% of RAM
        WHEN name = 'shared_buffers' THEN 'Recommend ~25% of total RAM'
        -- effective_cache_size: typically 50-75% of RAM
        WHEN name = 'effective_cache_size' THEN 'Recommend ~50-75% of total RAM'
        -- work_mem: depends on workload, typically 4-64MB
        WHEN name = 'work_mem' THEN 'Low values cause disk sorts; high values risk OOM with many connections'
        -- maintenance_work_mem: for VACUUM, CREATE INDEX
        WHEN name = 'maintenance_work_mem' THEN 'Higher = faster VACUUM/CREATE INDEX'
        -- random_page_cost: 1.1-1.5 for SSD, 4.0 for HDD
        WHEN name = 'random_page_cost' THEN 'Use 1.1-1.5 for SSD storage'
        -- effective_io_concurrency: higher for SSD
        WHEN name = 'effective_io_concurrency' THEN 'Use 200 for SSD storage'
        -- max_parallel_workers_per_gather
        WHEN name = 'max_parallel_workers_per_gather' THEN 'Enable parallelism for large scans'
        -- wal_buffers
        WHEN name = 'wal_buffers' THEN 'Usually auto-tuned; -1 = auto'
        -- checkpoint_completion_target
        WHEN name = 'checkpoint_completion_target' THEN 'Recommend 0.9'
        -- default_statistics_target
        WHEN name = 'default_statistics_target' THEN 'Higher = better estimates, slower ANALYZE'
        ELSE ''
    END AS guidance
FROM pg_settings
WHERE name IN (
    'shared_buffers', 'effective_cache_size', 'work_mem',
    'maintenance_work_mem', 'random_page_cost', 'effective_io_concurrency',
    'max_parallel_workers_per_gather', 'max_parallel_workers',
    'wal_buffers', 'checkpoint_completion_target', 'default_statistics_target',
    'max_connections', 'max_wal_size', 'min_wal_size'
)
ORDER BY name;

-- ---------------------------------------------------------------------------
-- 5. CHECKPOINT & WAL ACTIVITY
-- ---------------------------------------------------------------------------
SELECT
    'checkpoint_activity' AS section,
    num_timed AS checkpoints_timed,
    num_requested AS checkpoints_requested,
    CASE WHEN num_timed + num_requested > 0
         THEN ROUND(100.0 * num_requested / (num_timed + num_requested), 1)
         ELSE 0 END AS requested_pct,
    pg_size_pretty(buffers_written * 8192) AS buffers_at_checkpoint,
    pg_size_pretty(buffers_clean * 8192) AS buffers_cleaned,
    maxwritten_clean AS bgwriter_stops,
    pg_size_pretty(buffers_alloc * 8192) AS buffers_allocated
FROM pg_stat_checkpointer
CROSS JOIN pg_stat_bgwriter;
-- High checkpoints_requested % = max_wal_size may be too small
-- High buffers_allocated relative to cache size may indicate cache churn.
