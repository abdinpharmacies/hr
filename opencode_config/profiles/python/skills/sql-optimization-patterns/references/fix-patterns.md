# Fix Patterns

Ready-to-adapt SQL patterns for common root causes identified in Phase 2. Grab the pattern, adapt to your schema, verify semantic equivalence.

Each pattern includes: the problem signal, the fix template, and the index support it may need.

## N+1 Query Elimination

**Signal:** Many identical queries with different parameter values in quick succession.

### Batch Loading (replace loop with IN)

```sql
-- Instead of N individual queries:
--   SELECT * FROM orders WHERE user_id = 1;
--   SELECT * FROM orders WHERE user_id = 2; ...

-- Single batch query:
SELECT * FROM orders WHERE user_id IN (<id_list>);

-- Application side examples:
-- PostgreSQL parameterization:
SELECT * FROM orders WHERE user_id = ANY(:user_ids);

-- MySQL parameterization:
-- Build an IN (?, ?, ...) placeholder list in application code.

-- Python example:
user_ids = [u.id for u in users]
orders = db.query(
    "SELECT * FROM orders WHERE user_id = ANY(%s)",
    [user_ids]
)
-- Group in application code
orders_by_user = {}
for order in orders:
    orders_by_user.setdefault(order.user_id, []).append(order)
```

### JOIN Consolidation (merge into one query)

```sql
-- Fetch users and their orders in one round-trip
SELECT u.id, u.name, o.id AS order_id, o.total, o.status
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
WHERE u.id IN (<id_list>);

-- Index support:
CREATE INDEX idx_orders_user_id ON orders(user_id);
```

## Cursor-Based Pagination

**Signal:** Query uses `OFFSET N` with large N, and slows as user pages deeper.

### Keyset Pagination (single sort key)

```sql
-- Instead of:
--   SELECT * FROM posts ORDER BY created_at DESC LIMIT 20 OFFSET 10000;

-- Use cursor from last seen row:
SELECT id, title, created_at
FROM posts
WHERE created_at < :last_seen_created_at
ORDER BY created_at DESC
LIMIT 20;

-- Index support:
CREATE INDEX idx_posts_created_desc ON posts(created_at DESC);
```

### Keyset Pagination (composite cursor with tie-breaker)

```sql
-- When sort key is not unique (multiple rows with same created_at):
SELECT id, title, created_at
FROM posts
WHERE (created_at, id) < (:last_seen_created_at, :last_seen_id)
ORDER BY created_at DESC, id DESC
LIMIT 20;

-- Index support:
CREATE INDEX idx_posts_cursor ON posts(created_at DESC, id DESC);
```

## Correlated Subquery Rewrite

**Signal:** SubPlan node executing per outer row, or subquery in SELECT list.

### Scalar Subquery to JOIN

```sql
-- Instead of (correlated, runs per row):
SELECT u.name,
    (SELECT COUNT(*) FROM orders o WHERE o.user_id = u.id) AS order_count
FROM users u;

-- Rewrite as JOIN + GROUP BY:
SELECT u.name, COUNT(o.id) AS order_count
FROM users u
LEFT JOIN orders o ON o.user_id = u.id
GROUP BY u.id, u.name;
-- NOTE: Must use LEFT JOIN (not INNER JOIN) to preserve users with zero orders.
-- Must use COUNT(o.id) (not COUNT(*)) so NULLs from the LEFT JOIN produce 0, not 1.

-- Index support:
CREATE INDEX idx_orders_user_id ON orders(user_id);
```

### EXISTS Instead of COUNT for Boolean Check

```sql
-- Instead of:
SELECT * FROM users u
WHERE (SELECT COUNT(*) FROM orders o WHERE o.user_id = u.id) > 0;

-- Use EXISTS (stops at first match):
SELECT * FROM users u
WHERE EXISTS (SELECT 1 FROM orders o WHERE o.user_id = u.id);
```

### Lateral Join (PostgreSQL — when subquery needs to return multiple columns)

```sql
-- Get each user's most recent order
SELECT u.name, latest.total, latest.created_at
FROM users u
LEFT JOIN LATERAL (
    SELECT total, created_at
    FROM orders o
    WHERE o.user_id = u.id
    ORDER BY created_at DESC
    LIMIT 1
) latest ON true;

-- Index support:
CREATE INDEX idx_orders_user_created ON orders(user_id, created_at DESC);
```

## Aggregation Optimization

**Signal:** GroupAggregate or HashAggregate with large input, or `Using temporary` in MySQL.

### Filter Before Aggregation

```sql
-- Instead of aggregating everything then filtering:
SELECT user_id, COUNT(*) AS cnt
FROM orders
GROUP BY user_id
HAVING COUNT(*) > 10;

-- Filter the input first (if possible):
SELECT user_id, COUNT(*) AS cnt
FROM orders
WHERE status = 'completed'           -- reduce input rows
  AND created_at > NOW() - INTERVAL '90 days'  -- reduce further
GROUP BY user_id
HAVING COUNT(*) > 10;

-- Index support:
CREATE INDEX idx_orders_status_created ON orders(status, created_at);
```

### Approximate Count (PostgreSQL — when exact count not needed)

```sql
-- Instead of expensive exact count:
--   SELECT COUNT(*) FROM large_table;

-- Approximate from planner stats:
SELECT reltuples::bigint AS approx_rows
FROM pg_class
WHERE relname = 'large_table';

-- Or use HyperLogLog extensions for distinct counts (requires pg extension)
```

### Pre-Aggregated Materialized View (PostgreSQL — for dashboard queries)

```sql
-- Expensive query that runs frequently:
--   SELECT user_id, COUNT(*), SUM(total) FROM orders GROUP BY user_id;

-- Pre-compute (L2 — initial creation runs the full query and may block writes on
-- the source table during execution. Schedule during low-traffic or on staging first):
CREATE MATERIALIZED VIEW order_summary AS
SELECT user_id, COUNT(*) AS order_count, SUM(total) AS total_spent
FROM orders
GROUP BY user_id;

-- Required for REFRESH ... CONCURRENTLY:
CREATE UNIQUE INDEX idx_order_summary_user ON order_summary(user_id);

-- Refresh (schedule appropriately):
REFRESH MATERIALIZED VIEW CONCURRENTLY order_summary;
-- Note: CONCURRENTLY requires a unique index that covers each row uniquely
```

## Index Patterns

### Composite Index (column order matters)

```sql
-- For query: WHERE status = 'active' AND created_at > '2024-01-01'
-- Equality columns first, then range:
CREATE INDEX idx_orders_status_created ON orders(status, created_at);

-- For query: WHERE user_id = 123 ORDER BY created_at DESC
-- Filter column first, then sort column:
CREATE INDEX idx_orders_user_created ON orders(user_id, created_at DESC);
```

### Covering Index (PostgreSQL INCLUDE — avoids heap fetch)

```sql
-- Query only needs id, email, name — avoid going to table:
CREATE INDEX idx_users_email_covering ON users(email)
INCLUDE (name, created_at);

-- Turns Index Scan into Index Only Scan
```

### Partial Index (PostgreSQL — index only relevant rows)

```sql
-- Only 5% of users are active, and most queries filter by active:
CREATE INDEX idx_active_users ON users(email)
WHERE status = 'active';
-- Smaller index, faster lookups, less write overhead

-- Only index non-null values:
CREATE INDEX idx_orders_shipped ON orders(shipped_at)
WHERE shipped_at IS NOT NULL;
```

### Expression Index (index on computed value)

```sql
-- PostgreSQL:
CREATE INDEX idx_users_email_lower ON users(LOWER(email));
-- Query must match: WHERE LOWER(email) = 'user@example.com'

-- MySQL 8.0+:
CREATE INDEX idx_users_email_lower ON users((LOWER(email)));

-- MySQL <8.0 (generated column workaround):
ALTER TABLE users
  ADD COLUMN email_lower VARCHAR(255) GENERATED ALWAYS AS (LOWER(email)) STORED;
CREATE INDEX idx_users_email_lower ON users(email_lower);
```

### GIN Index (PostgreSQL — JSONB, arrays, full-text)

```sql
-- JSONB containment queries:
CREATE INDEX idx_events_metadata ON events USING GIN(metadata);
-- Supports: WHERE metadata @> '{"type": "click"}'

-- Array containment:
CREATE INDEX idx_posts_tags ON posts USING GIN(tags);
-- Supports: WHERE tags @> ARRAY['sql']

-- Full-text search:
CREATE INDEX idx_posts_search ON posts
USING GIN(to_tsvector('english', title || ' ' || body));
-- Supports: WHERE to_tsvector('english', title || ' ' || body) @@ to_tsquery('optimization')
```

## Batch Operations

### Batch INSERT

```sql
-- Instead of N individual INSERTs, use multi-value:
INSERT INTO users (name, email) VALUES
    ('Alice', 'alice@example.com'),
    ('Bob', 'bob@example.com'),
    ('Carol', 'carol@example.com');

-- PostgreSQL bulk: COPY (fastest for large loads)
COPY users (name, email) FROM '/tmp/users.csv' CSV HEADER;

-- PostgreSQL: UNNEST for parameterized batch from application
INSERT INTO users (name, email)
SELECT * FROM UNNEST(
    ARRAY['Alice', 'Bob', 'Carol'],
    ARRAY['alice@example.com', 'bob@example.com', 'carol@example.com']
);
```

### Batch UPDATE (from values list)

```sql
-- PostgreSQL: UPDATE from VALUES
UPDATE orders o
SET status = v.new_status
FROM (VALUES (1, 'shipped'), (2, 'delivered'), (3, 'cancelled')) AS v(id, new_status)
WHERE o.id = v.id;

-- MySQL: CASE-based batch update
-- WARNING: The WHERE IN clause is mandatory. Without it, the CASE's implicit
-- ELSE NULL sets status=NULL on every row not listed in the WHEN clauses.
UPDATE orders
SET status = CASE id
    WHEN 1 THEN 'shipped'
    WHEN 2 THEN 'delivered'
    WHEN 3 THEN 'cancelled'
END
WHERE id IN (1, 2, 3);
```

### Chunked Large Updates (L4 — avoid long locks, wrap each chunk in a transaction)

```sql
-- Instead of one massive UPDATE that locks the table:
--   UPDATE orders SET archived = true WHERE created_at < '2023-01-01';

-- Process in chunks (each chunk is its own transaction for safe rollback):
-- PostgreSQL:
BEGIN;
WITH batch AS (
    SELECT id FROM orders
    WHERE created_at < '2023-01-01' AND archived = false
    LIMIT 1000
    FOR UPDATE SKIP LOCKED
)
UPDATE orders SET archived = true
WHERE id IN (SELECT id FROM batch);
COMMIT;
-- Repeat until 0 rows affected. If a chunk fails, only that chunk rolls back.

-- MySQL:
START TRANSACTION;
UPDATE orders SET archived = true
WHERE created_at < '2023-01-01' AND archived = false
LIMIT 1000;
COMMIT;
-- Repeat until 0 rows affected.
```

## UPSERT (Insert or Update)

```sql
-- PostgreSQL:
INSERT INTO user_stats (user_id, login_count, last_login)
VALUES (123, 1, NOW())
ON CONFLICT (user_id) DO UPDATE
SET login_count = user_stats.login_count + 1,
    last_login = EXCLUDED.last_login;

-- MySQL:
INSERT INTO user_stats (user_id, login_count, last_login)
VALUES (123, 1, NOW())
ON DUPLICATE KEY UPDATE
    login_count = login_count + 1,
    last_login = VALUES(last_login);
```

## Window Function Patterns

### Row Number for Deduplication (L4 — data deletion, requires backup)

**WARNING: This pattern permanently deletes data. A wrong PARTITION BY or ORDER BY silently deletes the wrong rows with no recovery path.**

```sql
-- Step 1: DRY RUN — verify which rows would be deleted (L0, safe)
SELECT id, user_id, created_at FROM (
    SELECT id, user_id, created_at, ROW_NUMBER() OVER (
        PARTITION BY user_id
        ORDER BY created_at DESC
    ) AS rn
    FROM user_events
) ranked
WHERE rn > 1
ORDER BY user_id, created_at DESC;
-- Review the output carefully. Verify row count matches expectations.

-- Step 2: EXECUTE — only after backup confirmation and dry-run review
BEGIN;
DELETE FROM user_events
WHERE id IN (
    SELECT id FROM (
        SELECT id, ROW_NUMBER() OVER (
            PARTITION BY user_id
            ORDER BY created_at DESC
        ) AS rn
        FROM user_events
    ) ranked
    WHERE rn > 1
);
-- Verify row count matches dry run before committing:
-- COMMIT;   -- uncomment only after verification
-- ROLLBACK; -- use this if counts don't match
```

### Running Totals Without Self-Join

```sql
-- Instead of correlated subquery for running total:
SELECT
    id, amount,
    SUM(amount) OVER (ORDER BY created_at ROWS UNBOUNDED PRECEDING) AS running_total
FROM transactions
WHERE user_id = 123;
```
