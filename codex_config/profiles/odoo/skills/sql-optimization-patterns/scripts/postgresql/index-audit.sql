-- =============================================================================
-- PostgreSQL Index Audit (L0 — read-only, safe to run anywhere)
-- =============================================================================
-- Comprehensive index analysis: unused, duplicate, overlapping, invalid,
-- missing candidates, bloat, and B-Tree specific health.
-- Run as a monitoring/read-only role.
--
-- Sections:
--   1. Index Overview (per table)
--   2. Unused Indexes (zero scans)
--   3. Rarely Used Indexes (low scan count)
--   4. Duplicate Index Candidates (same key columns)
--   5. Overlapping Index Candidates (one key list is prefix of another)
--   6. Invalid Indexes (failed CONCURRENTLY)
--   7. Missing Index Candidates (high seq scan on large tables)
--   8. Index vs Table Size Ratio
--   9. Write-Heavy Tables (index overhead concern)
--  10. B-Tree Specific: Bloat Estimation
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. INDEX OVERVIEW (per table)
-- ---------------------------------------------------------------------------
SELECT
    'index_overview' AS section,
    t.schemaname,
    t.relname AS table_name,
    pg_size_pretty(pg_relation_size(t.relid)) AS table_size,
    pg_size_pretty(pg_indexes_size(t.relid)) AS total_index_size,
    CASE WHEN pg_relation_size(t.relid) > 0
         THEN ROUND(100.0 * pg_indexes_size(t.relid) / pg_relation_size(t.relid), 1)
         ELSE 0 END AS index_to_table_pct,
    (SELECT COUNT(*) FROM pg_indexes WHERE tablename = t.relname AND schemaname = t.schemaname) AS index_count,
    t.seq_scan,
    t.idx_scan,
    CASE WHEN t.seq_scan + t.idx_scan > 0
         THEN ROUND(100.0 * t.idx_scan / (t.seq_scan + t.idx_scan), 1)
         ELSE 0 END AS idx_scan_pct
FROM pg_stat_user_tables t
ORDER BY pg_total_relation_size(t.relid) DESC;

-- ---------------------------------------------------------------------------
-- 2. UNUSED INDEXES (zero scans since stats reset)
-- ---------------------------------------------------------------------------
-- These indexes cost write performance and storage but provide no read benefit.
-- Verify stats haven't been recently reset before dropping.
SELECT
    'unused_indexes' AS section,
    schemaname,
    relname AS table_name,
    indexrelname AS index_name,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size,
    pg_relation_size(indexrelid) AS index_size_bytes,
    idx_scan AS times_used
FROM pg_stat_user_indexes
WHERE idx_scan = 0
  AND indexrelname NOT LIKE '%_pkey'        -- keep primary keys
  AND indexrelname NOT LIKE '%_unique%'     -- keep unique constraints (review case by case)
ORDER BY pg_relation_size(indexrelid) DESC;

-- Total space wasted by unused indexes
SELECT
    'unused_index_total' AS section,
    COUNT(*) AS unused_count,
    pg_size_pretty(SUM(pg_relation_size(indexrelid))) AS total_wasted_size
FROM pg_stat_user_indexes
WHERE idx_scan = 0
  AND indexrelname NOT LIKE '%_pkey';

-- ---------------------------------------------------------------------------
-- 3. RARELY USED INDEXES (< 50 scans — may not justify write overhead)
-- ---------------------------------------------------------------------------
SELECT
    'rarely_used_indexes' AS section,
    schemaname,
    relname AS table_name,
    indexrelname AS index_name,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size,
    idx_scan AS times_used,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
WHERE idx_scan BETWEEN 1 AND 50
  AND indexrelname NOT LIKE '%_pkey'
ORDER BY idx_scan ASC, pg_relation_size(indexrelid) DESC
LIMIT 20;

-- ---------------------------------------------------------------------------
-- 4. DUPLICATE INDEX CANDIDATES (heuristic only)
-- This comparison is intentionally coarse: it matches key columns only.
-- Review predicates, sort direction, operator classes, INCLUDE columns,
-- expressions, and uniqueness before treating any row as redundant.
-- ---------------------------------------------------------------------------
SELECT
    'duplicate_indexes' AS section,
    a.indrelid::regclass AS table_name,
    a.indexrelid::regclass AS index_a,
    b.indexrelid::regclass AS index_b,
    pg_size_pretty(pg_relation_size(a.indexrelid)) AS size_a,
    pg_size_pretty(pg_relation_size(b.indexrelid)) AS size_b,
    pg_get_indexdef(a.indexrelid) AS def_a,
    pg_get_indexdef(b.indexrelid) AS def_b
FROM pg_index a
JOIN pg_index b
    ON a.indrelid = b.indrelid
    AND a.indexrelid != b.indexrelid
    AND a.indkey::text = b.indkey::text  -- key columns only; semantics may still differ
WHERE a.indexrelid < b.indexrelid        -- avoid showing both directions
ORDER BY a.indrelid::regclass::text, pg_relation_size(a.indexrelid) DESC;

-- ---------------------------------------------------------------------------
-- 5. OVERLAPPING INDEX CANDIDATES (heuristic only)
-- ---------------------------------------------------------------------------
-- Example: idx(a, b) may make idx(a) redundant for some queries, but confirm
-- predicates, sort order, and access patterns before recommending removal.
SELECT
    'overlapping_indexes' AS section,
    a.indrelid::regclass AS table_name,
    a.indexrelid::regclass AS shorter_index,
    b.indexrelid::regclass AS longer_index,
    pg_size_pretty(pg_relation_size(a.indexrelid)) AS shorter_size,
    pg_get_indexdef(a.indexrelid) AS shorter_def,
    pg_get_indexdef(b.indexrelid) AS longer_def
FROM pg_index a
JOIN pg_index b
    ON a.indrelid = b.indrelid
    AND a.indexrelid != b.indexrelid
    AND a.indkey::text != b.indkey::text
    AND b.indkey::text LIKE a.indkey::text || ' %'  -- a's columns are prefix of b's
WHERE NOT a.indisunique  -- don't flag unique constraints
ORDER BY a.indrelid::regclass::text, pg_relation_size(a.indexrelid) DESC;

-- ---------------------------------------------------------------------------
-- 6. INVALID INDEXES (from failed CREATE INDEX CONCURRENTLY)
-- ---------------------------------------------------------------------------
-- These indexes consume space and slow writes but are never used by the planner.
-- Safe to drop and retry.
SELECT
    'invalid_indexes' AS section,
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexname::regclass)) AS index_size,
    indexdef
FROM pg_indexes
JOIN pg_index ON pg_index.indexrelid = (schemaname || '.' || indexname)::regclass
WHERE NOT pg_index.indisvalid;

-- ---------------------------------------------------------------------------
-- 7. MISSING INDEX CANDIDATES (high seq scan on large tables)
-- ---------------------------------------------------------------------------
-- Tables with frequent sequential scans and many rows scanned per scan.
-- Strong signal that an index is needed.
SELECT
    'missing_index_candidates' AS section,
    schemaname,
    relname AS table_name,
    seq_scan,
    seq_tup_read,
    CASE WHEN seq_scan > 0
         THEN seq_tup_read / seq_scan
         ELSE 0 END AS avg_rows_per_seq_scan,
    idx_scan,
    n_live_tup AS live_rows,
    pg_size_pretty(pg_relation_size(relid)) AS table_size
FROM pg_stat_user_tables
WHERE seq_scan > 10                        -- at least some activity
  AND n_live_tup > 10000                   -- large enough to matter
  AND (idx_scan = 0                        -- no index scans at all
       OR (seq_scan > idx_scan * 10))      -- seq scans dominate heavily
ORDER BY seq_tup_read DESC
LIMIT 15;

-- ---------------------------------------------------------------------------
-- 8. INDEX vs TABLE SIZE RATIO (over-indexed tables)
-- ---------------------------------------------------------------------------
-- Tables where indexes are larger than the table itself — may be over-indexed
SELECT
    'over_indexed_tables' AS section,
    schemaname,
    relname AS table_name,
    pg_size_pretty(pg_relation_size(relid)) AS table_size,
    pg_size_pretty(pg_indexes_size(relid)) AS indexes_size,
    ROUND(100.0 * pg_indexes_size(relid) / GREATEST(pg_relation_size(relid), 1), 1) AS index_to_table_pct,
    (SELECT COUNT(*) FROM pg_indexes WHERE tablename = relname AND schemaname = t.schemaname) AS index_count
FROM pg_stat_user_tables t
WHERE pg_indexes_size(relid) > pg_relation_size(relid)
  AND pg_relation_size(relid) > 1048576  -- >1MB (skip tiny tables)
ORDER BY pg_indexes_size(relid) DESC;

-- ---------------------------------------------------------------------------
-- 9. WRITE-HEAVY TABLES (index overhead is most costly here)
-- ---------------------------------------------------------------------------
-- Tables with high write rates. Each index slows every INSERT/UPDATE/DELETE.
SELECT
    'write_heavy_tables' AS section,
    schemaname,
    relname AS table_name,
    n_tup_ins AS inserts,
    n_tup_upd AS updates,
    n_tup_del AS deletes,
    n_tup_ins + n_tup_upd + n_tup_del AS total_writes,
    n_tup_hot_upd AS hot_updates,
    CASE WHEN n_tup_upd > 0
         THEN ROUND(100.0 * n_tup_hot_upd / n_tup_upd, 1)
         ELSE 0 END AS hot_update_pct,
    (SELECT COUNT(*) FROM pg_indexes WHERE tablename = relname AND schemaname = t.schemaname) AS index_count
FROM pg_stat_user_tables t
WHERE n_tup_ins + n_tup_upd + n_tup_del > 1000
ORDER BY (n_tup_ins + n_tup_upd + n_tup_del) DESC
LIMIT 15;

-- ---------------------------------------------------------------------------
-- 10. B-TREE BLOAT ESTIMATION
-- ---------------------------------------------------------------------------
-- Estimates bloat in B-Tree indexes by comparing actual size to expected size.
-- Based on a simplified version of the pgstattuple approach.
-- Note: This is an ESTIMATE. For precise measurement, use pgstattuple extension.
SELECT
    'btree_bloat_estimate' AS section,
    nspname AS schema,
    tblname AS table_name,
    idxname AS index_name,
    pg_size_pretty(real_size) AS actual_size,
    pg_size_pretty(estimated_size) AS estimated_needed,
    CASE WHEN real_size > 0
         THEN ROUND(100.0 * (real_size - estimated_size) / real_size, 1)
         ELSE 0 END AS bloat_pct,
    pg_size_pretty(real_size - estimated_size) AS bloat_size
FROM (
    SELECT
        n.nspname,
        ct.relname AS tblname,
        ci.relname AS idxname,
        pg_relation_size(ci.oid) AS real_size,
        -- Rough estimate: (live tuples * avg index entry width) * fill factor overhead
        COALESCE(
            (ct.reltuples * (
                -- avg width: sum of indexed column widths + 8 bytes overhead per entry
                (SELECT SUM(COALESCE(sta.avg_width, 8))
                 FROM pg_index ix
                 CROSS JOIN LATERAL UNNEST(ix.indkey) WITH ORDINALITY AS k(attnum, ord)
                 JOIN pg_attribute a ON a.attrelid = ix.indrelid AND a.attnum = k.attnum
                 LEFT JOIN pg_stats sta ON sta.tablename = ct.relname
                     AND sta.attname = a.attname AND sta.schemaname = n.nspname
                 WHERE ix.indexrelid = ci.oid
                ) + 8
            ) * 1.2  -- ~20% overhead for B-Tree internal nodes and fill factor
            )::bigint,
            0
        ) AS estimated_size
    FROM pg_class ci
    JOIN pg_index i ON ci.oid = i.indexrelid
    JOIN pg_class ct ON ct.oid = i.indrelid
    JOIN pg_namespace n ON n.oid = ct.relnamespace
    WHERE ci.relam = (SELECT oid FROM pg_am WHERE amname = 'btree')
      AND n.nspname NOT IN ('pg_catalog', 'information_schema')
      AND ct.reltuples > 1000  -- skip tiny tables
      AND pg_relation_size(ci.oid) > 65536  -- skip tiny indexes (< 64KB)
) AS bloat_data
WHERE real_size > estimated_size * 1.5  -- only show indexes with >50% estimated bloat
ORDER BY (real_size - estimated_size) DESC
LIMIT 15;
