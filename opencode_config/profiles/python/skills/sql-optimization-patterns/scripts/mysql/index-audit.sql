-- =============================================================================
-- MySQL Index Audit (L0 — read-only, heuristic review aid)
-- =============================================================================
-- Comprehensive index analysis: unused, duplicate, missing candidates,
-- cardinality issues, and write overhead assessment.
-- Requires MySQL 8.0+ with performance_schema enabled for usage stats.
-- Duplicate/redundant sections are intentionally coarse and should be treated
-- as review candidates, not direct drop recommendations.
--
-- Sections:
--   1. Index Overview (per table)
--   2. Unused Indexes (zero reads)
--   3. Duplicate Index Candidates (same column set)
--   4. Redundant Index Candidates (prefix overlap)
--   5. Low Cardinality Indexes (poor selectivity)
--   6. Missing Index Candidates (full table scans)
--   7. Over-Indexed Tables
--   8. Write-Heavy Tables (index overhead concern)
--   9. Index Size Analysis
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. INDEX OVERVIEW (per table)
-- ---------------------------------------------------------------------------
SELECT
    'index_overview' AS section,
    t.table_name,
    t.engine,
    t.table_rows AS estimated_rows,
    ROUND(t.data_length / 1024 / 1024, 2) AS data_mb,
    ROUND(t.index_length / 1024 / 1024, 2) AS index_mb,
    CASE WHEN t.data_length > 0
         THEN ROUND(100.0 * t.index_length / t.data_length, 1)
         ELSE 0 END AS index_to_data_pct,
    (SELECT COUNT(DISTINCT index_name)
     FROM information_schema.statistics s
     WHERE s.table_schema = t.table_schema AND s.table_name = t.table_name) AS index_count
FROM information_schema.tables t
WHERE t.table_schema = DATABASE()
  AND t.table_type = 'BASE TABLE'
ORDER BY (t.data_length + t.index_length) DESC;

-- ---------------------------------------------------------------------------
-- 2. UNUSED INDEXES (zero reads — requires performance_schema)
-- ---------------------------------------------------------------------------
SELECT
    'unused_indexes' AS section,
    object_name AS table_name,
    index_name,
    count_read AS read_ops,
    count_write AS write_ops,
    count_fetch AS fetch_ops
FROM performance_schema.table_io_waits_summary_by_index_usage
WHERE object_schema = DATABASE()
  AND index_name IS NOT NULL
  AND index_name != 'PRIMARY'
  AND count_read = 0
ORDER BY count_write DESC;

-- Total write overhead from unused indexes (estimated by write count)
SELECT
    'unused_index_write_overhead' AS section,
    COUNT(*) AS unused_index_count,
    SUM(count_write) AS total_wasted_writes
FROM performance_schema.table_io_waits_summary_by_index_usage
WHERE object_schema = DATABASE()
  AND index_name IS NOT NULL
  AND index_name != 'PRIMARY'
  AND count_read = 0;

-- ---------------------------------------------------------------------------
-- 3. DUPLICATE INDEX CANDIDATES (heuristic only)
-- This compares ordered key column names only. Review uniqueness, prefix
-- lengths, expression/generator semantics, visibility, and engine behavior
-- before recommending removal.
-- ---------------------------------------------------------------------------
SELECT
    'duplicate_indexes' AS section,
    a.table_name,
    a.index_name AS index_a,
    b.index_name AS index_b,
    a.columns AS column_list
FROM (
    SELECT table_schema, table_name, index_name,
           GROUP_CONCAT(column_name ORDER BY seq_in_index) AS columns
    FROM information_schema.statistics
    WHERE table_schema = DATABASE()
    GROUP BY table_schema, table_name, index_name
) a
JOIN (
    SELECT table_schema, table_name, index_name,
           GROUP_CONCAT(column_name ORDER BY seq_in_index) AS columns
    FROM information_schema.statistics
    WHERE table_schema = DATABASE()
    GROUP BY table_schema, table_name, index_name
) b ON a.table_schema = b.table_schema
    AND a.table_name = b.table_name
    AND a.columns = b.columns
    AND a.index_name < b.index_name
ORDER BY a.table_name;

-- ---------------------------------------------------------------------------
-- 4. REDUNDANT INDEX CANDIDATES (heuristic only)
-- ---------------------------------------------------------------------------
-- Example: INDEX(a) may be redundant if INDEX(a, b) exists, but confirm
-- uniqueness, prefix lengths, and workload shape before dropping anything.
SELECT
    'redundant_indexes' AS section,
    a.table_name,
    a.index_name AS shorter_index,
    a.columns AS shorter_columns,
    b.index_name AS longer_index,
    b.columns AS longer_columns
FROM (
    SELECT table_schema, table_name, index_name,
           GROUP_CONCAT(column_name ORDER BY seq_in_index) AS columns
    FROM information_schema.statistics
    WHERE table_schema = DATABASE()
      AND non_unique = 1  -- don't flag unique constraints
    GROUP BY table_schema, table_name, index_name
) a
JOIN (
    SELECT table_schema, table_name, index_name,
           GROUP_CONCAT(column_name ORDER BY seq_in_index) AS columns
    FROM information_schema.statistics
    WHERE table_schema = DATABASE()
    GROUP BY table_schema, table_name, index_name
) b ON a.table_schema = b.table_schema
    AND a.table_name = b.table_name
    AND a.index_name != b.index_name
    AND b.columns LIKE CONCAT(a.columns, ',%')
ORDER BY a.table_name, a.index_name;

-- ---------------------------------------------------------------------------
-- 5. LOW CARDINALITY INDEX CANDIDATES (review workload before acting)
-- ---------------------------------------------------------------------------
-- Indexes where the number of distinct values is very low relative to row count.
-- These indexes may not be useful for the optimizer.
SELECT
    'low_cardinality_indexes' AS section,
    table_name,
    index_name,
    column_name,
    seq_in_index,
    cardinality,
    (SELECT table_rows FROM information_schema.tables t
     WHERE t.table_schema = s.table_schema AND t.table_name = s.table_name) AS table_rows,
    CASE WHEN (SELECT table_rows FROM information_schema.tables t
               WHERE t.table_schema = s.table_schema AND t.table_name = s.table_name) > 0
         THEN ROUND(100.0 * cardinality /
              (SELECT table_rows FROM information_schema.tables t
               WHERE t.table_schema = s.table_schema AND t.table_name = s.table_name), 1)
         ELSE 0 END AS selectivity_pct
FROM information_schema.statistics s
WHERE table_schema = DATABASE()
  AND seq_in_index = 1  -- leading column
  AND cardinality IS NOT NULL
  AND (SELECT table_rows FROM information_schema.tables t
       WHERE t.table_schema = s.table_schema AND t.table_name = s.table_name) > 1000
  AND cardinality < (SELECT table_rows FROM information_schema.tables t
       WHERE t.table_schema = s.table_schema AND t.table_name = s.table_name) * 0.01
ORDER BY selectivity_pct ASC
LIMIT 15;

-- ---------------------------------------------------------------------------
-- 6. MISSING INDEX CANDIDATES (queries doing full table scans)
-- ---------------------------------------------------------------------------
-- Tables with high full-scan activity (from performance_schema)
SELECT
    'full_scan_tables' AS section,
    object_name AS table_name,
    count_read AS total_read_ops,
    count_fetch AS fetch_ops_no_index,
    ROUND(100.0 * count_fetch / GREATEST(count_read, 1), 1) AS full_scan_pct
FROM performance_schema.table_io_waits_summary_by_table
WHERE object_schema = DATABASE()
  AND count_read > 100
  AND count_fetch > count_read * 0.5  -- more than 50% are full scans
ORDER BY count_fetch DESC
LIMIT 15;

-- Queries causing full table scans (from events_statements)
SELECT
    'full_scan_queries' AS section,
    DIGEST_TEXT AS query_pattern,
    COUNT_STAR AS executions,
    SUM_NO_INDEX_USED AS scans_no_index,
    SUM_NO_GOOD_INDEX_USED AS scans_bad_index,
    ROUND(SUM_TIMER_WAIT / 1e12, 2) AS total_sec,
    SUM_ROWS_EXAMINED AS rows_examined,
    SUM_ROWS_SENT AS rows_sent
FROM performance_schema.events_statements_summary_by_digest
WHERE SCHEMA_NAME = DATABASE()
  AND (SUM_NO_INDEX_USED > 0 OR SUM_NO_GOOD_INDEX_USED > 0)
ORDER BY SUM_NO_INDEX_USED DESC
LIMIT 15;

-- ---------------------------------------------------------------------------
-- 7. OVER-INDEXED TABLES (index size > data size)
-- ---------------------------------------------------------------------------
SELECT
    'over_indexed_tables' AS section,
    table_name,
    engine,
    ROUND(data_length / 1024 / 1024, 2) AS data_mb,
    ROUND(index_length / 1024 / 1024, 2) AS index_mb,
    ROUND(100.0 * index_length / GREATEST(data_length, 1), 1) AS index_to_data_pct,
    (SELECT COUNT(DISTINCT index_name)
     FROM information_schema.statistics s
     WHERE s.table_schema = DATABASE() AND s.table_name = t.table_name) AS index_count
FROM information_schema.tables t
WHERE table_schema = DATABASE()
  AND table_type = 'BASE TABLE'
  AND index_length > data_length
  AND data_length > 1048576  -- >1MB
ORDER BY index_length DESC;

-- ---------------------------------------------------------------------------
-- 8. WRITE-HEAVY TABLES (index overhead concern)
-- ---------------------------------------------------------------------------
SELECT
    'write_heavy_tables' AS section,
    object_name AS table_name,
    count_write AS total_write_ops,
    count_read AS total_read_ops,
    CASE WHEN count_read > 0
         THEN ROUND(count_write / count_read, 2)
         ELSE count_write END AS write_to_read_ratio,
    (SELECT COUNT(DISTINCT index_name)
     FROM information_schema.statistics s
     WHERE s.table_schema = DATABASE() AND s.table_name = t.object_name) AS index_count
FROM performance_schema.table_io_waits_summary_by_table t
WHERE object_schema = DATABASE()
  AND count_write > 1000
ORDER BY count_write DESC
LIMIT 15;

-- ---------------------------------------------------------------------------
-- 9. INDEX SIZE ANALYSIS
-- ---------------------------------------------------------------------------
-- Individual index sizes (approximate from statistics)
SELECT
    'index_sizes' AS section,
    table_name,
    index_name,
    GROUP_CONCAT(column_name ORDER BY seq_in_index) AS columns,
    MAX(cardinality) AS max_cardinality,
    CASE WHEN non_unique = 0 THEN 'UNIQUE' ELSE 'NON-UNIQUE' END AS uniqueness
FROM information_schema.statistics
WHERE table_schema = DATABASE()
GROUP BY table_name, index_name, non_unique
ORDER BY table_name, index_name;
