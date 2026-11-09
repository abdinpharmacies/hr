-- =============================================================================
-- MariaDB Security Audit (L0 — read-only, privileged metadata access required)
-- =============================================================================
-- Scans for common security risks: overprivileged accounts, cross-database
-- access, weak authentication indicators, and data exposure patterns.
-- Requires MariaDB metadata access to mysql.* and information_schema grants.
-- This script is read-only, but it is not expected to succeed under a minimal
-- monitoring role.
--
-- Sections:
--   1. User & Privilege Overview
--   2. Superuser / ALL PRIVILEGES Accounts
--   3. Cross-Database Access
--   4. Users Without Password / Weak Auth
--   5. Host-Based Access
--   6. Grant Chaining (WITH GRANT OPTION)
--   7. Global Privileges (dangerous grants)
--   8. Definer-Based Stored Routines
--   9. SSL/TLS Connection Status
--  10. Schema Exposure Assessment
-- =============================================================================

SELECT
    'user_overview' AS section,
    user,
    host,
    password_expired,
    plugin AS auth_plugin,
    ssl_type,
    CASE
        WHEN plugin = 'mysql_native_password' THEN 'REVIEW: legacy auth plugin'
        WHEN plugin = 'ed25519' THEN 'ok: stronger password auth plugin'
        WHEN plugin = 'unix_socket' THEN 'ok: OS-level auth'
        ELSE plugin
    END AS auth_note
FROM mysql.user
WHERE user NOT LIKE 'mysql.%'
ORDER BY user, host;

SELECT
    'superuser_accounts' AS section,
    grantee,
    privilege_type,
    is_grantable
FROM information_schema.user_privileges
WHERE privilege_type IN ('SUPER', 'ALL PRIVILEGES', 'CREATE USER', 'RELOAD', 'SHUTDOWN', 'FILE')
ORDER BY grantee, privilege_type;

SELECT
    'cross_database_access' AS section,
    grantee,
    table_schema AS database_name,
    GROUP_CONCAT(DISTINCT privilege_type ORDER BY privilege_type) AS privileges
FROM information_schema.schema_privileges
WHERE table_schema NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
GROUP BY grantee, table_schema
ORDER BY grantee, table_schema;

SELECT
    'wildcard_database_grants' AS section,
    user,
    host,
    db AS database_pattern
FROM mysql.db
WHERE db LIKE '%\%%'
ORDER BY user;

SELECT
    'no_password_accounts' AS section,
    user,
    host,
    plugin AS auth_plugin,
    CASE
        WHEN authentication_string = '' OR authentication_string IS NULL
        THEN 'NO PASSWORD SET'
        ELSE 'password set'
    END AS password_status
FROM mysql.user
WHERE user NOT LIKE 'mysql.%'
  AND (authentication_string = '' OR authentication_string IS NULL)
ORDER BY user;

SELECT
    'expired_passwords' AS section,
    user,
    host,
    password_expired
FROM mysql.user
WHERE password_expired = 'Y'
  AND user NOT LIKE 'mysql.%';

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

SELECT
    'dangerous_global_privileges' AS section,
    grantee,
    privilege_type,
    CASE
        WHEN privilege_type = 'FILE' THEN 'Can read/write files on server filesystem'
        WHEN privilege_type = 'PROCESS' THEN 'Can see all queries from all users'
        WHEN privilege_type = 'SUPER' THEN 'Can bypass normal safety checks'
        WHEN privilege_type = 'RELOAD' THEN 'Can flush logs, privileges, tables'
        WHEN privilege_type = 'SHUTDOWN' THEN 'Can shut down the server'
        WHEN privilege_type = 'CREATE USER' THEN 'Can create and drop any user'
        ELSE ''
    END AS risk_description
FROM information_schema.user_privileges
WHERE privilege_type IN ('FILE', 'PROCESS', 'SUPER', 'RELOAD', 'SHUTDOWN', 'CREATE USER')
ORDER BY privilege_type, grantee;

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

SELECT
    'current_connection_ssl' AS section,
    @@ssl_cipher AS current_cipher,
    CASE WHEN COALESCE(@@ssl_cipher, '') != '' THEN 'encrypted' ELSE 'UNENCRYPTED' END AS status;

SELECT
    'ssl_config' AS section,
    @@require_secure_transport AS require_ssl,
    @@ssl_ca AS ca_file,
    @@ssl_cert AS cert_file,
    @@ssl_cipher AS current_cipher,
    @@tls_version AS tls_versions;

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

SELECT
    'table_exposure' AS section,
    table_name,
    grantee,
    GROUP_CONCAT(DISTINCT privilege_type ORDER BY privilege_type) AS privileges
FROM information_schema.table_privileges
WHERE table_schema = DATABASE()
GROUP BY table_name, grantee
ORDER BY table_name, grantee;

SELECT
    'schema_level_grants' AS section,
    grantee,
    privilege_type
FROM information_schema.schema_privileges
WHERE table_schema = DATABASE()
ORDER BY grantee, privilege_type;
