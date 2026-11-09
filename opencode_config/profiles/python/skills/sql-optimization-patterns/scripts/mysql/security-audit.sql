-- =============================================================================
-- MySQL Security Audit (L0 — read-only, privileged metadata access required)
-- =============================================================================
-- Scans for common security risks: overprivileged accounts, cross-database
-- access, weak authentication, and data exposure patterns.
-- Requires MySQL 8.0+ for some features.
-- Requires an admin or security-audit role with access to mysql.* metadata.
-- This script is read-only, but it is not expected to succeed under a minimal
-- monitoring role.
--
-- Sections:
--   1. User & Privilege Overview
--   2. Superuser / ALL PRIVILEGES Accounts
--   3. Cross-Database Access (accounts accessing unrelated databases)
--   4. Users Without Password / Weak Auth
--   5. Host-Based Access (overly permissive host patterns)
--   6. Grant Chaining (WITH GRANT OPTION)
--   7. Global Privileges (dangerous grants)
--   8. Definer-Based Stored Routines (privilege escalation)
--   9. SSL/TLS Connection Status
--  10. Schema Exposure Assessment
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. USER & PRIVILEGE OVERVIEW
-- ---------------------------------------------------------------------------
SELECT
    'user_overview' AS section,
    user,
    host,
    account_locked,
    password_expired,
    password_last_changed,
    password_lifetime,
    plugin AS auth_plugin,
    CASE
        WHEN plugin = 'mysql_native_password' THEN 'REVIEW: legacy auth plugin'
        WHEN plugin = 'caching_sha2_password' THEN 'ok: modern auth'
        WHEN plugin = 'auth_socket' THEN 'ok: OS-level auth'
        ELSE plugin
    END AS auth_note
FROM mysql.user
WHERE user NOT LIKE 'mysql.%'
ORDER BY user, host;

-- ---------------------------------------------------------------------------
-- 2. SUPERUSER / ALL PRIVILEGES ACCOUNTS
-- ---------------------------------------------------------------------------
-- Accounts with SUPER or ALL PRIVILEGES — minimize these
SELECT
    'superuser_accounts' AS section,
    grantee,
    privilege_type,
    is_grantable
FROM information_schema.user_privileges
WHERE privilege_type IN ('SUPER', 'ALL PRIVILEGES', 'CREATE USER', 'RELOAD', 'SHUTDOWN', 'FILE')
ORDER BY grantee, privilege_type;

-- ---------------------------------------------------------------------------
-- 3. CROSS-DATABASE ACCESS
-- ---------------------------------------------------------------------------
-- Accounts with privileges on databases other than the current one.
-- Flag if a service account should only access its own database.
SELECT
    'cross_database_access' AS section,
    grantee,
    table_schema AS database_name,
    GROUP_CONCAT(DISTINCT privilege_type) AS privileges
FROM information_schema.schema_privileges
WHERE table_schema NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
GROUP BY grantee, table_schema
ORDER BY grantee, table_schema;

-- Accounts with wildcard database grants (%)
SELECT
    'wildcard_database_grants' AS section,
    user,
    host,
    db AS database_pattern
FROM mysql.db
WHERE db LIKE '%\%%'
ORDER BY user;

-- ---------------------------------------------------------------------------
-- 4. USERS WITHOUT PASSWORD / WEAK AUTH
-- ---------------------------------------------------------------------------
-- Accounts that might have empty passwords or no authentication
SELECT
    'no_password_accounts' AS section,
    user,
    host,
    plugin AS auth_plugin,
    account_locked,
    CASE
        WHEN authentication_string = '' OR authentication_string IS NULL
        THEN 'NO PASSWORD SET'
        ELSE 'password set'
    END AS password_status
FROM mysql.user
WHERE user NOT LIKE 'mysql.%'
  AND (authentication_string = '' OR authentication_string IS NULL)
ORDER BY user;

-- Accounts with expired passwords
SELECT
    'expired_passwords' AS section,
    user,
    host,
    password_expired,
    password_last_changed,
    password_lifetime
FROM mysql.user
WHERE password_expired = 'Y'
  AND user NOT LIKE 'mysql.%';

-- ---------------------------------------------------------------------------
-- 5. HOST-BASED ACCESS (overly permissive host patterns)
-- ---------------------------------------------------------------------------
-- Accounts accessible from any host (%) — should be restricted to specific IPs/networks
SELECT
    'permissive_host_access' AS section,
    user,
    host,
    CASE
        WHEN host = '%' THEN 'OPEN TO ALL HOSTS — restrict to specific IPs'
        WHEN host LIKE '%\%%' THEN 'WILDCARD HOST — review scope'
        WHEN host = 'localhost' OR host = '127.0.0.1' THEN 'ok: local only'
        ELSE 'specific host'
    END AS risk_note
FROM mysql.user
WHERE user NOT LIKE 'mysql.%'
  AND user != ''
ORDER BY
    CASE WHEN host = '%' THEN 0 WHEN host LIKE '%\%%' THEN 1 ELSE 2 END,
    user;

-- ---------------------------------------------------------------------------
-- 6. GRANT CHAINING (WITH GRANT OPTION)
-- ---------------------------------------------------------------------------
-- Accounts that can grant their privileges to others — privilege escalation path
SELECT
    'grant_option_accounts' AS section,
    grantee,
    table_schema,
    privilege_type,
    is_grantable
FROM information_schema.schema_privileges
WHERE is_grantable = 'YES'
  AND table_schema NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
ORDER BY grantee;

SELECT
    'grant_option_global' AS section,
    grantee,
    privilege_type,
    is_grantable
FROM information_schema.user_privileges
WHERE is_grantable = 'YES'
ORDER BY grantee;

-- ---------------------------------------------------------------------------
-- 7. GLOBAL PRIVILEGES (dangerous grants)
-- ---------------------------------------------------------------------------
-- Accounts with FILE, PROCESS, or other dangerous global privileges
SELECT
    'dangerous_global_privileges' AS section,
    grantee,
    privilege_type,
    CASE
        WHEN privilege_type = 'FILE' THEN 'Can read/write files on server filesystem'
        WHEN privilege_type = 'PROCESS' THEN 'Can see all queries from all users'
        WHEN privilege_type = 'SUPER' THEN 'Can kill queries, change global vars, skip checks'
        WHEN privilege_type = 'RELOAD' THEN 'Can flush logs, privileges, tables'
        WHEN privilege_type = 'SHUTDOWN' THEN 'Can shut down the server'
        WHEN privilege_type = 'CREATE USER' THEN 'Can create and drop any user'
        ELSE ''
    END AS risk_description
FROM information_schema.user_privileges
WHERE privilege_type IN ('FILE', 'PROCESS', 'SUPER', 'RELOAD', 'SHUTDOWN', 'CREATE USER')
ORDER BY privilege_type, grantee;

-- ---------------------------------------------------------------------------
-- 8. DEFINER-BASED STORED ROUTINES (privilege escalation risk)
-- ---------------------------------------------------------------------------
-- Routines that run with definer privileges (SQL SECURITY DEFINER).
-- If definer has higher privileges than invoker, this is an escalation path.
SELECT
    'security_definer_routines' AS section,
    routine_schema,
    routine_name,
    routine_type,
    definer,
    security_type,
    CASE
        WHEN security_type = 'DEFINER' THEN 'REVIEW: runs with definer privileges'
        ELSE 'ok: runs with invoker privileges'
    END AS risk_note
FROM information_schema.routines
WHERE routine_schema = DATABASE()
  AND security_type = 'DEFINER'
ORDER BY routine_type, routine_name;

-- Views with DEFINER security
SELECT
    'security_definer_views' AS section,
    table_schema,
    table_name AS view_name,
    definer,
    security_type,
    CASE
        WHEN security_type = 'DEFINER' THEN 'REVIEW: runs with definer privileges'
        ELSE 'ok: runs with invoker privileges'
    END AS risk_note
FROM information_schema.views
WHERE table_schema = DATABASE()
  AND security_type = 'DEFINER'
ORDER BY table_name;

-- ---------------------------------------------------------------------------
-- 9. SSL/TLS CONNECTION STATUS
-- ---------------------------------------------------------------------------
-- Check current connection encryption
SELECT
    'current_connection_ssl' AS section,
    @@ssl_cipher AS current_cipher,
    CASE WHEN @@ssl_cipher != '' THEN 'encrypted' ELSE 'UNENCRYPTED' END AS status;

-- SSL configuration
SELECT
    'ssl_config' AS section,
    @@require_secure_transport AS require_ssl,
    @@ssl_ca AS ca_file,
    @@ssl_cert AS cert_file,
    @@ssl_cipher AS current_cipher,
    @@tls_version AS tls_versions;

-- Users that require SSL
SELECT
    'ssl_required_users' AS section,
    user,
    host,
    ssl_type,
    CASE
        WHEN ssl_type = '' THEN 'NO SSL REQUIRED'
        WHEN ssl_type = 'ANY' THEN 'any SSL'
        WHEN ssl_type = 'X509' THEN 'X509 cert required'
        WHEN ssl_type = 'SPECIFIED' THEN 'specific cipher/issuer/subject'
        ELSE ssl_type
    END AS ssl_requirement
FROM mysql.user
WHERE user NOT LIKE 'mysql.%'
  AND user != ''
ORDER BY ssl_type, user;

-- ---------------------------------------------------------------------------
-- 10. SCHEMA EXPOSURE ASSESSMENT
-- ---------------------------------------------------------------------------
-- Tables in current database with broad access grants
SELECT
    'table_exposure' AS section,
    table_name,
    grantee,
    GROUP_CONCAT(DISTINCT privilege_type ORDER BY privilege_type) AS privileges
FROM information_schema.table_privileges
WHERE table_schema = DATABASE()
GROUP BY table_name, grantee
ORDER BY table_name, grantee;

-- Check if any user can access all tables (schema-level grants)
SELECT
    'schema_level_grants' AS section,
    grantee,
    privilege_type
FROM information_schema.schema_privileges
WHERE table_schema = DATABASE()
ORDER BY grantee, privilege_type;
