-- =============================================================================
-- PostgreSQL Security Audit (L0 — read-only, version-aware metadata audit)
-- =============================================================================
-- Scans for common security risks: overprivileged roles, public exposure,
-- cross-database access, authentication review prompts, and data exposure patterns.
-- Run as a monitoring role (some sections require elevated privileges for full
-- results). Authentication policy cannot be inferred reliably from role
-- catalogs alone; review pg_hba.conf and any external auth integration
-- separately.
--
-- Sections:
--   1. Role & Privilege Overview
--   2. Superuser Accounts
--   3. Roles with CREATEDB / CREATEROLE
--   4. Authentication Configuration Review Note
--   5. Cross-Database Access (roles with access to other databases)
--   6. Public Schema Exposure
--   7. Tables Accessible to PUBLIC
--   8. Overly Permissive Column Grants
--   9. Functions with SECURITY DEFINER (privilege escalation risk)
--  10. Unencrypted Connection Check
--  11. Row-Level Security (RLS) Coverage
--  12. Extensions Audit
--  13. Search Path Hijack Risk
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. ROLE & PRIVILEGE OVERVIEW
-- ---------------------------------------------------------------------------
SELECT
    'role_overview' AS section,
    rolname AS role_name,
    rolsuper AS is_superuser,
    rolcreaterole AS can_create_roles,
    rolcreatedb AS can_create_db,
    rolcanlogin AS can_login,
    rolreplication AS is_replication,
    rolbypassrls AS bypasses_rls,
    rolconnlimit AS conn_limit,
    rolvaliduntil AS password_expires
FROM pg_roles
WHERE rolname NOT LIKE 'pg_%'
ORDER BY rolsuper DESC, rolcreatedb DESC, rolcreaterole DESC, rolcanlogin DESC;

-- Role memberships (who inherits which privileges)
SELECT
    'role_memberships' AS section,
    r.rolname AS member_role,
    m.rolname AS member_of,
    a.admin_option
FROM pg_auth_members a
JOIN pg_roles r ON r.oid = a.member
JOIN pg_roles m ON m.oid = a.roleid
WHERE r.rolname NOT LIKE 'pg_%'
ORDER BY r.rolname;

-- ---------------------------------------------------------------------------
-- 2. SUPERUSER ACCOUNTS
-- ---------------------------------------------------------------------------
-- Every superuser is a risk. There should be as few as possible.
SELECT
    'superusers' AS section,
    rolname AS role_name,
    rolcanlogin AS can_login,
    rolvaliduntil AS password_expires,
    CASE WHEN rolvaliduntil IS NOT NULL AND rolvaliduntil < NOW()
         THEN 'EXPIRED' ELSE 'active' END AS status
FROM pg_roles
WHERE rolsuper = true
ORDER BY rolname;

-- ---------------------------------------------------------------------------
-- 3. ROLES WITH CREATEDB / CREATEROLE (privilege escalation surface)
-- ---------------------------------------------------------------------------
SELECT
    'privilege_escalation_roles' AS section,
    rolname AS role_name,
    rolcreatedb AS can_create_db,
    rolcreaterole AS can_create_roles,
    rolcanlogin AS can_login
FROM pg_roles
WHERE (rolcreatedb = true OR rolcreaterole = true)
  AND rolsuper = false
  AND rolname NOT LIKE 'pg_%';

-- ---------------------------------------------------------------------------
-- 4. AUTHENTICATION CONFIGURATION REVIEW NOTE
-- ---------------------------------------------------------------------------
-- PostgreSQL authentication posture depends on pg_hba.conf, external identity
-- providers, and version-specific catalog behavior. Do not infer password
-- policy from pg_roles alone.
SELECT
    'authentication_review_note' AS section,
    current_database() AS database_name,
    'Review pg_hba.conf, TLS requirements, and external auth configuration separately; pg_roles alone is insufficient for password-policy conclusions.' AS note;

-- ---------------------------------------------------------------------------
-- 5. CROSS-DATABASE ACCESS
-- ---------------------------------------------------------------------------
-- Roles that have CONNECT privilege on databases other than the current one.
-- Flag if a role should only access one specific database.
SELECT
    'cross_database_access' AS section,
    r.rolname AS role_name,
    d.datname AS database_name,
    HAS_DATABASE_PRIVILEGE(r.rolname, d.datname, 'CONNECT') AS can_connect
FROM pg_roles r
CROSS JOIN pg_database d
WHERE r.rolcanlogin = true
  AND r.rolname NOT LIKE 'pg_%'
  AND r.rolsuper = false
  AND d.datallowconn = true
  AND d.datname != 'template0'
  AND HAS_DATABASE_PRIVILEGE(r.rolname, d.datname, 'CONNECT') = true
ORDER BY r.rolname, d.datname;

-- ---------------------------------------------------------------------------
-- 6. PUBLIC SCHEMA EXPOSURE
-- ---------------------------------------------------------------------------
-- Check if the public schema has default privileges that allow any user
-- to create objects (common misconfiguration).
SELECT
    'public_schema_privileges' AS section,
    nspname AS schema_name,
    nspacl AS access_control_list
FROM pg_namespace
WHERE nspname = 'public';

-- Default privileges that might be too open
SELECT
    'default_privileges' AS section,
    pg_get_userbyid(defaclrole) AS granting_role,
    defaclnamespace::regnamespace AS schema,
    defaclobjtype AS object_type,
    defaclacl AS access_control_list
FROM pg_default_acl
WHERE defaclacl::text LIKE '%=r/%'       -- read access
   OR defaclacl::text LIKE '%=arwdDxt/%' -- broad access
ORDER BY defaclrole;

-- ---------------------------------------------------------------------------
-- 7. TABLES ACCESSIBLE TO PUBLIC (any logged-in user can read)
-- ---------------------------------------------------------------------------
SELECT
    'public_accessible_tables' AS section,
    schemaname,
    tablename,
    tableowner,
    ARRAY(
        SELECT privilege_type
        FROM information_schema.table_privileges
        WHERE table_schema = t.schemaname
          AND table_name = t.tablename
          AND grantee = 'PUBLIC'
    ) AS public_privileges
FROM pg_tables t
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
  AND EXISTS (
      SELECT 1 FROM information_schema.table_privileges
      WHERE table_schema = t.schemaname
        AND table_name = t.tablename
        AND grantee = 'PUBLIC'
  )
ORDER BY schemaname, tablename;

-- ---------------------------------------------------------------------------
-- 8. OVERLY PERMISSIVE COLUMN-LEVEL GRANTS
-- ---------------------------------------------------------------------------
-- Columns where specific users have been granted access.
-- Not necessarily bad, but review for least-privilege compliance.
SELECT
    'column_grants' AS section,
    table_schema,
    table_name,
    column_name,
    grantee,
    privilege_type
FROM information_schema.column_privileges
WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
  AND grantee != current_user
  AND grantee != 'PUBLIC'
ORDER BY table_schema, table_name, column_name;

-- ---------------------------------------------------------------------------
-- 9. FUNCTIONS WITH SECURITY DEFINER (privilege escalation risk)
-- ---------------------------------------------------------------------------
-- SECURITY DEFINER functions run with the privileges of the function owner,
-- not the caller. If the owner is a superuser, this is a privilege escalation vector.
SELECT
    'security_definer_functions' AS section,
    n.nspname AS schema,
    p.proname AS function_name,
    pg_get_userbyid(p.proowner) AS owner,
    r.rolsuper AS owner_is_superuser,
    pg_get_function_arguments(p.oid) AS arguments,
    p.prosecdef AS is_security_definer
FROM pg_proc p
JOIN pg_namespace n ON n.oid = p.pronamespace
JOIN pg_roles r ON r.oid = p.proowner
WHERE p.prosecdef = true
  AND n.nspname NOT IN ('pg_catalog', 'information_schema')
ORDER BY n.nspname, p.proname;

-- ---------------------------------------------------------------------------
-- 10. UNENCRYPTED CONNECTION CHECK
-- ---------------------------------------------------------------------------
-- Check if current connection and other active connections use SSL.
SELECT
    'connection_encryption' AS section,
    pid,
    usename,
    client_addr,
    ssl,
    CASE WHEN ssl THEN 'encrypted' ELSE 'UNENCRYPTED' END AS status
FROM pg_stat_ssl
JOIN pg_stat_activity USING (pid)
WHERE pid != pg_backend_pid()
  AND datname = current_database()
ORDER BY ssl ASC;

-- Check current connection
SELECT
    'current_connection_ssl' AS section,
    COALESCE(
        (SELECT ssl
         FROM pg_stat_ssl
         WHERE pid = pg_backend_pid()),
        false
    ) AS current_conn_uses_ssl;

-- ---------------------------------------------------------------------------
-- 11. ROW-LEVEL SECURITY (RLS) COVERAGE
-- ---------------------------------------------------------------------------
-- Tables WITHOUT RLS enabled. Not every table needs RLS, but for multi-tenant
-- or sensitive data, missing RLS is a risk. Flag for review.
SELECT
    'tables_without_rls' AS section,
    n.nspname AS schemaname,
    c.relname AS tablename,
    c.relrowsecurity AS rls_enabled,
    c.relforcerowsecurity AS rls_forced
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
  AND c.relkind IN ('r', 'p')
  AND NOT c.relrowsecurity
ORDER BY n.nspname, c.relname;

-- Tables WITH RLS but no policies defined (RLS enabled but effectively denies all)
SELECT
    'rls_no_policies' AS section,
    n.nspname AS schemaname,
    c.relname AS tablename
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
  AND c.relkind IN ('r', 'p')
  AND c.relrowsecurity = true
  AND NOT EXISTS (
      SELECT 1
      FROM pg_policies p
      WHERE p.tablename = c.relname
        AND p.schemaname = n.nspname
  );

-- ---------------------------------------------------------------------------
-- 12. EXTENSIONS AUDIT
-- ---------------------------------------------------------------------------
-- List all installed extensions. Some extensions have security implications.
SELECT
    'installed_extensions' AS section,
    extname AS extension_name,
    extversion AS version,
    nspname AS schema,
    CASE
        WHEN extname IN ('dblink', 'postgres_fdw', 'file_fdw') THEN 'REVIEW: enables cross-system access'
        WHEN extname IN ('adminpack') THEN 'REVIEW: admin capabilities'
        WHEN extname = 'plpythonu' THEN 'REVIEW: untrusted language — can run OS commands'
        WHEN extname = 'plperlu' THEN 'REVIEW: untrusted language — can run OS commands'
        ELSE 'ok'
    END AS security_note
FROM pg_extension e
JOIN pg_namespace n ON n.oid = e.extnamespace
ORDER BY extname;

-- ---------------------------------------------------------------------------
-- 13. SEARCH PATH HIJACK RISK
-- ---------------------------------------------------------------------------
-- If search_path includes schemas where unprivileged users can create objects,
-- a user could shadow system functions with malicious versions.
SELECT
    'search_path_config' AS section,
    name,
    setting,
    CASE
        WHEN setting LIKE '%"$user"%' OR setting LIKE '%public%'
        THEN 'REVIEW: includes user-writable schemas — potential hijack vector'
        ELSE 'ok'
    END AS risk_note
FROM pg_settings
WHERE name = 'search_path';
