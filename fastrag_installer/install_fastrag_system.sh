#!/usr/bin/env bash
# Install the PostgreSQL-backed FastRAG service on a local systemd host.
set +x
set -euo pipefail
umask 077
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
unset PYTHONPATH PYTHONHOME

readonly ACCOUNT=fastrag DATABASE=fastrag ROOT=/opt/fastrag
readonly VENV=$ROOT/venv-fast CONFIG=$ROOT/config/config.pgvector.yaml
readonly KEYS=$ROOT/keys ODOO_KEY=$ROOT/keys/odoo.key
readonly UNIT_NAME=fastrag.service UNIT=/etc/systemd/system/fastrag.service
readonly PG_SOCKET=/var/run/postgresql PG_PORT=5432 PORT=8111
readonly SOURCE="$(dirname -- "$(realpath -- "${BASH_SOURCE[0]}")")"
readonly DSN="host=$PG_SOCKET port=$PG_PORT dbname=$DATABASE user=$ACCOUNT"

die() { printf 'FastRAG: %s\n' "$*" >&2; exit 1; }
present() { [[ -e $1 || -L $1 ]]; }
sql() {
    runuser -u postgres -- env -i PATH="$PATH" PGPASSFILE=/dev/null \
        psql -XwqAt --set=ON_ERROR_STOP=1 --host="$PG_SOCKET" --port="$PG_PORT" "$@"
}
app() {
    release_app "$ROOT" "$@"
}
release_app() {
    local release=$1
    shift
    (cd "$release" && runuser -u "$ACCOUNT" -- env -i PATH="$PATH" HOME="$ROOT" \
        PYTHONDONTWRITEBYTECODE=1 PGPASSFILE=/dev/null "$release/venv-fast/bin/python" -m app "$@")
}
root_dir() {
    [[ -d $1 && ! -L $1 && $(stat -c '%u' -- "$1") == 0 ]] || return 1
    local mode
    mode=$(stat -c '%a' -- "$1")
    (( (8#$mode & 0022) == 0 ))
}
choose() {
    local answer
    while true; do
        printf 'Existing %s. [s]kip / [o]verwrite / [a]bort: ' "$1" >&2
        read -r answer </dev/tty || die 'No interactive terminal; no decisions were applied.'
        case ${answer,,} in
            s|skip) choice=skip; return ;;
            o|overwrite) choice=overwrite; return ;;
            a|abort) die 'Aborted before changes.' ;;
            *) printf 'Enter s, o, or a.\n' >&2 ;;
        esac
    done
}

unit_text() {
    local release=${1:-$ROOT}
    cat <<UNIT_FILE
[Unit]
Description=FastRAG API and pgvector indexing worker
After=postgresql.service network-online.target
Wants=network-online.target postgresql.service

[Service]
Type=simple
User=fastrag
Group=fastrag
WorkingDirectory=$release
Environment=HOME=/opt/fastrag
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=PGPASSFILE=/dev/null
ExecStart=$release/venv-fast/bin/python -m app serve --config $CONFIG
Restart=on-failure
RestartSec=5
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
TimeoutStopSec=90

[Install]
WantedBy=multi-user.target
UNIT_FILE
}

build_venv() (
    umask 022
    python3 -I -m venv "$1"
    "$1/bin/python" -I -m pip --isolated install -r "$2"
    "$1/bin/python" -I -m pip --isolated check
)

verify_config() {
    runuser -u "$ACCOUNT" -- env -i PATH="$PATH" HOME="$ROOT" \
        "$1/bin/python" -I - "$CONFIG" "$DSN" "$PORT" <<'PY'
import sys
import yaml
from psycopg.conninfo import conninfo_to_dict

try:
    with open(sys.argv[1], encoding="utf-8") as stream:
        cfg = yaml.safe_load(stream)
    assert cfg["storage"] == "pgvector"
    assert conninfo_to_dict(cfg["database"]["dsn"]) == conninfo_to_dict(sys.argv[2])
    assert cfg["server"]["host"] == "127.0.0.1" and cfg["server"]["port"] == int(sys.argv[3])
except Exception:
    sys.exit("Config must be readable by fastrag, use the local fastrag peer DSN, and bind 127.0.0.1:8111.")
PY
}

verify_config_file() {
    local config_mode
    root_dir "$ROOT/config" || die 'The config directory must be real and root-owned (not group/world writable).'
    [[ -f $CONFIG && ! -L $CONFIG ]] || die 'Refusing to use a missing, non-regular or symlinked config.'
    [[ $(stat -c '%u:%G' -- "$CONFIG") == "0:$ACCOUNT" ]] || die 'Config must be owned by root:fastrag.'
    config_mode=$(stat -c '%a' -- "$CONFIG")
    (( (8#$config_mode & 0037) == 0 )) || die 'Config must not be group-writable or accessible to other users.'
}

verify_peer() {
    local identity
    identity=$(runuser -u "$ACCOUNT" -- env -i PATH="$PATH" PGPASSFILE=/dev/null \
        psql -XwqAt --host="$PG_SOCKET" --port="$PG_PORT" -U "$ACCOUNT" -d "$DATABASE" -c 'SELECT SYSTEM_USER') \
        || die 'Passwordless socket login failed. Verify pg_hba.conf permits local peer auth for fastrag; no rules were changed.'
    [[ $identity == "peer:$ACCOUNT" ]] || die 'The local Pg connection did not use peer authentication.'
}

verify_key_file() {
    [[ -d $KEYS && ! -L $KEYS && $(stat -c '%U:%a' -- "$KEYS") == "$ACCOUNT:700" ]] \
        || die "$KEYS must be a real directory owned by $ACCOUNT with mode 0700."
    [[ -f $ODOO_KEY && ! -L $ODOO_KEY && -s $ODOO_KEY ]] \
        || die "$ODOO_KEY must be a non-empty regular file, not a symlink."
    local key_mode
    key_mode=$(stat -c '%a' -- "$ODOO_KEY")
    (( (8#$key_mode & 0077) == 0 )) || die "$ODOO_KEY must not be accessible by group or other users."
}

ready() {
    local key status
    systemctl is-active --quiet "$UNIT_NAME" || return 1
    # Keep the bearer token out of arguments, the environment, and output.
    key=$(runuser -u "$ACCOUNT" -- cat -- "$ODOO_KEY") || return 1
    [[ $key =~ ^[A-Za-z0-9_-]+$ ]] || return 1
    status=$(printf 'Authorization: Bearer %s\n' "$key" | curl -q --silent --noproxy '*' \
        --max-time 2 --header @- --output /dev/null --write-out '%{http_code}' \
        "http://127.0.0.1:$PORT/readyz") && [[ $status == 200 ]]
}

wait_ready() {
    local attempt
    for (( attempt=0; attempt<20; attempt++ )); do
        if ready; then return 0; fi
        sleep 1
    done
    return 1
}

upgrade() (
    releases=$ROOT/releases
    current=$ROOT/current
    previous=
    previous_link=
    scratch=
    rollback=0
    unit_changed=0
    pointer_changed=0

    root_dir /opt && root_dir "$ROOT" || die 'Unsafe installation directory.'
    [[ $SOURCE != "$ROOT" && $SOURCE != "$ROOT/"* ]] || die 'Run --upgrade from a new source tree or bundle outside /opt/fastrag.'
    [[ $(systemctl show -p FragmentPath --value "$UNIT_NAME") == "$UNIT" && -f $UNIT && ! -L $UNIT ]] \
        || die 'Upgrade requires the local installer-managed systemd unit.'
    [[ -z $(systemctl show -p DropInPaths --value "$UNIT_NAME") &&
       $(systemctl show -p NeedDaemonReload --value "$UNIT_NAME") == no ]] \
        || die 'Review systemd drop-ins or pending unit changes before upgrading.'
    if present "$current"; then
        root_dir "$releases" && [[ -L $current ]] || die 'Unsafe release layout.'
        previous_link=$(readlink -- "$current")
        [[ $previous_link =~ ^releases/release\.[A-Za-z0-9]+$ ]] || die 'Unexpected current release link.'
        previous=$ROOT/$previous_link
        cmp -s "$UNIT" <(unit_text "$current") || die 'The installed systemd unit has been customized.'
    else
        previous=$ROOT
        cmp -s "$UNIT" <(unit_text) || die 'Expected the original pgvector installer unit.'
    fi
    root_dir "$previous" && root_dir "$previous/app" && root_dir "$previous/venv-fast" \
        || die 'The current release is not secured.'
    verify_config_file
    verify_key_file
    ready || die 'The existing service is not ready with its saved Odoo key. Fix it before upgrading.'
    if present "$SOURCE/SHA256SUMS"; then
        [[ -f $SOURCE/SHA256SUMS && ! -L $SOURCE/SHA256SUMS ]] || die 'Unsafe bundle checksum manifest.'
        (cd "$SOURCE" && sha256sum --check --strict --quiet SHA256SUMS) || die 'Bundle checksum verification failed.'
    fi
    cmp -s "$SOURCE/app/pg_schema.sql" "$previous/app/pg_schema.sql" \
        || die 'This release changes the database schema. Plan the migration separately; no service changes were made.'

    if ! present "$releases"; then install -d -m 0755 "$releases"; fi
    root_dir "$releases" || die 'Unsafe releases directory.'
    candidate=$(mktemp -d "$releases/release.XXXXXXXX")
    chmod 0755 "$candidate"
    printf 'Preparing release %s while FastRAG is running.\n' "$candidate"
    install -d -m 0755 "$candidate/app"
    for file in "$SOURCE"/app/*.py "$SOURCE"/app/{requirements.txt,requirements-pgvector.txt,pg_schema.sql}; do
        [[ -f $file && ! -L $file ]] || die "Missing or unsafe release file: $file"
        install -m 0644 "$file" "$candidate/app/"
    done
    [[ -f $candidate/app/__main__.py && -f $candidate/app/pg_api.py ]] || die 'Incomplete application release.'
    build_venv "$candidate/venv-fast" "$candidate/app/requirements-pgvector.txt"
    verify_config "$candidate/venv-fast"
    verify_peer
    release_app "$candidate" check --config "$CONFIG"

    finish_upgrade() {
        local status=$?
        trap - EXIT
        trap '' HUP INT TERM
        if (( rollback )); then
            printf 'Upgrade failed; restoring the previous FastRAG release.\n' >&2
            if systemctl stop "$UNIT_NAME" &&
                restore_release &&
                systemctl daemon-reload &&
                systemctl start "$UNIT_NAME" &&
                wait_ready; then
                printf 'Previous FastRAG release is ready again.\n' >&2
            else
                printf 'Automatic recovery failed. Inspect journalctl -u %s and recovery files in %s.\n' \
                    "$UNIT_NAME" "$scratch" >&2
                exit 1
            fi
        fi
        if [[ -n $scratch ]]; then
            rm -f -- "$scratch/$UNIT_NAME" "$scratch/previous.unit"
            rmdir -- "$scratch"
        fi
        if [[ -n ${link_dir:-} ]]; then
            rm -f -- "$link_dir/current" "$link_dir/previous"
            rmdir -- "$link_dir"
        fi
        exit "$status"
    }
    restore_release() {
        if (( pointer_changed )); then
            if [[ -n $previous_link ]]; then
                mv -Tf -- "$link_dir/previous" "$current" || return 1
            else
                rm -f -- "$current" || return 1
            fi
        fi
        if (( unit_changed )); then
            mv -Tf -- "$scratch/previous.unit" "$UNIT" || return 1
        fi
    }
    trap finish_upgrade EXIT
    trap 'exit 1' HUP INT TERM
    scratch=$(mktemp -d "$(dirname -- "$UNIT")/.fastrag-upgrade.XXXXXXXX")
    link_dir=$(mktemp -d "$ROOT/.fastrag-upgrade.XXXXXXXX")
    ln -s -- "releases/${candidate##*/}" "$link_dir/current"
    if [[ -n $previous_link ]]; then ln -s -- "$previous_link" "$link_dir/previous"; fi
    if [[ -z $previous_link ]]; then
        install -m 0644 "$UNIT" "$scratch/previous.unit"
    fi
    unit_text "$candidate" >"$scratch/$UNIT_NAME"
    systemd-analyze verify "$scratch/$UNIT_NAME"
    unit_text "$current" >"$scratch/$UNIT_NAME"
    chmod 0644 "$scratch/$UNIT_NAME"
    ready || die 'The existing service stopped being ready during preparation; upgrade not activated.'

    rollback=1
    systemctl stop "$UNIT_NAME"
    pointer_changed=1
    mv -Tf -- "$link_dir/current" "$current"
    if [[ -z $previous_link ]]; then
        unit_changed=1
        mv -Tf -- "$scratch/$UNIT_NAME" "$UNIT"
        systemctl daemon-reload
    fi
    systemctl start "$UNIT_NAME"
    wait_ready || die 'The new FastRAG release did not pass authenticated readiness.'
    rollback=0
    printf 'FastRAG upgrade complete: %s (previous release retained at %s)\n' "$candidate" "$previous"
    exit 0
)

case ${1:-} in
    --help|-h)
        printf 'Usage: sudo bash install_fastrag_system.sh [--check|--upgrade]\n'
        printf 'Install FastRAG in /opt/fastrag. --check inventories the host without making changes.\n'
        printf '%s\n' '--upgrade stages a new app release and rolls back if it does not become ready.'
        exit 0 ;;
    ''|--check|--upgrade) (( $# <= 1 )) || die 'Use --help for usage.' ;;
    *) die 'Unknown argument. Use --help.' ;;
esac
(( EUID == 0 )) || die 'Run this installer with sudo.'
for cmd in python3 psql runuser systemctl systemd-analyze curl ss useradd usermod groupadd \
    getent flock mktemp stat cmp install; do
    command -v "$cmd" >/dev/null || die "Missing $cmd; see docs/PGVECTOR.md."
done
python3 -I -c 'import ensurepip; assert __import__("sys").version_info >= (3, 12)' \
    || die 'Install Python 3.12+ and its venv package (python3-venv on Ubuntu).'
[[ -f $SOURCE/app/pg_schema.sql && -f $SOURCE/app/requirements-pgvector.txt ]] \
    || die 'Keep the app directory beside this script: use the full FastRAG project or a portable installer bundle.'
[[ -d /run/systemd/system ]] || die 'This installer needs a running systemd host.'
if ! root_dir /opt; then
    printf 'Warning: /opt is not a private root-owned parent. Only trusted admins should be able to replace /opt/fastrag.\n' >&2
fi
root_dir /etc/systemd/system || die 'Unsafe systemd unit directory.'
sql -d postgres -c 'SELECT 1' >/dev/null || die 'Cannot reach local PostgreSQL as postgres.'
[[ $(sql -d postgres -c "SELECT count(*) FROM pg_available_extensions WHERE name='vector'") == 1 ]] \
    || die 'Install the pgvector package for the running PostgreSQL server.'

if [[ ${1:-} != --check ]]; then
    [[ ${1:-} == --upgrade || -t 0 ]] || die 'Run this installer interactively.'
    # Prevent concurrent provisioning attempts on this host.
    exec 9>/run/lock/fastrag-system-install.lock
    flock -n 9 || die 'Another FastRAG install is running.'
fi
if [[ ${1:-} == --upgrade ]]; then upgrade; exit; fi
if [[ ${1:-} != --check ]] && present "$ROOT/current"; then
    die 'This installation uses versioned releases. Run the new bundle with --upgrade.'
fi

os_user=0 group=0 home=0 pg_role=0 pg_db=0 pg_vector=0 project=0 venv=0 unit=0
if getent passwd "$ACCOUNT" >/dev/null; then os_user=1; fi
if getent group "$ACCOUNT" >/dev/null; then group=1; fi
if present "$ROOT"; then home=1; fi
pg_role=$(sql -d postgres -c "SELECT count(*) FROM pg_roles WHERE rolname='fastrag'")
pg_db=$(sql -d postgres -c "SELECT count(*) FROM pg_database WHERE datname='fastrag'")
if (( pg_db )); then
    pg_vector=$(sql -d "$DATABASE" -c "SELECT count(*) FROM pg_extension WHERE extname='vector'")
fi
readonly -a project_items=(app deploy docs tests README.md AGENTS.md install-fastrag.sh install_fastrag_system.sh \
    config/config.example.yaml config/config.pgvector.example.yaml .gitignore)
for item in "${project_items[@]}"; do
    if present "$ROOT/$item"; then project=1; break; fi
done
if present "$VENV"; then venv=1; fi
load_state=$(systemctl show -p LoadState --value "$UNIT_NAME") || die 'Cannot query systemd.'
if present "$UNIT" || [[ $load_state != not-found ]]; then unit=1; fi
printf 'Existing resources (1=yes): user=%s group=%s home=%s project=%s venv=%s role=%s db=%s vector=%s unit=%s\n' \
    "$os_user" "$group" "$home" "$project" "$venv" "$pg_role" "$pg_db" "$pg_vector" "$unit"
if [[ ${1:-} == --check ]]; then exit 0; fi

printf '%s\n' 'Overwrite reconciles accounts and DB settings in place; it never drops the database or its records.' \
    'Replaced project files, virtual environment, and local unit are moved to a private backup. Live config stays in place.'
for goal in os_user group home project venv pg_role pg_db pg_vector unit; do
    choice=create
    if (( ${!goal} )); then
        case $goal in
            os_user) label="system user $ACCOUNT" ;;
            group) label="system group $ACCOUNT (membership is preserved)" ;;
            home) label="$ROOT home directory (contents are preserved)" ;;
            project) label="project files in $ROOT" ;;
            venv) label="virtual environment $VENV" ;;
            pg_role) label="PostgreSQL role $ACCOUNT" ;;
            pg_db) label="PostgreSQL database $DATABASE (data is preserved)" ;;
            pg_vector) label="vector extension in $DATABASE (overwrite means upgrade in place)" ;;
            unit) label="systemd unit $UNIT_NAME" ;;
        esac
        choose "$label"
    fi
    printf -v "do_$goal" '%s' "$choice"
done

# Refuse unsafe or incompatible reuse rather than running someone else's code or
# transferring ownership of an unrelated database.
if (( home )); then
    [[ -d $ROOT && ! -L $ROOT ]] || die "$ROOT is not a real directory."
    if [[ $do_home == skip ]]; then root_dir "$ROOT" || die 'Skipped home is not secured; choose overwrite to fix it.'; fi
fi
if present "$ROOT/config"; then root_dir "$ROOT/config" || die 'The existing config directory must be real and root-owned (not group/world writable).'; fi
if present "$CONFIG"; then verify_config_file; fi
if [[ $SOURCE == "$ROOT" && $do_project != skip ]]; then die 'Re-copy from the original project or a portable bundle, not /opt/fastrag.'; fi
if [[ $do_project == skip ]]; then
    root_dir "$ROOT/app" && [[ -r $ROOT/app/pg_schema.sql && -r $ROOT/app/requirements-pgvector.txt ]] \
        || die 'Skipped project does not contain a secured pgvector application.'
fi
if [[ $do_venv == skip ]]; then
    root_dir "$VENV" && [[ -f $VENV/pyvenv.cfg && -x $VENV/bin/python ]] || die 'Skipped venv is not usable.'
fi
if (( group )); then
    group_entry=$(getent -s files group "$ACCOUNT") || die 'Existing group is not locally managed.'
    IFS=: read -r _ _ group_id members <<<"$group_entry"
    [[ -z $members || $members == "$ACCOUNT" ]] || die 'Existing fastrag group has other members.'
    [[ -z $(getent passwd | awk -F: -v gid="$group_id" '$4 == gid && $1 != "fastrag" { print $1 }') ]] \
        || die 'Existing fastrag group is shared with another user.'
fi
if (( os_user )); then
    account_entry=$(getent -s files passwd "$ACCOUNT") || die 'Existing account is not locally managed.'
    IFS=: read -r _ _ uid gid _ account_home shell <<<"$account_entry"
    (( uid > 0 && gid > 0 )) || die 'Refusing to reuse a privileged system account.'
    [[ $shell == /usr/sbin/nologin || $shell == /sbin/nologin ]] \
        || die 'Existing FastRAG account has a login shell; review it manually before reuse.'
    if [[ $do_os_user == skip ]]; then
        [[ $account_home == "$ROOT" ]] && (( group )) && [[ $(id -gn "$ACCOUNT") == "$ACCOUNT" ]] \
            || die 'Skipped account does not have the requested home and primary group.'
    fi
fi
if (( pg_role )); then
    [[ $(sql -d postgres -c "SELECT count(*) FROM pg_roles r WHERE rolname='fastrag'
      AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls
           OR EXISTS (SELECT 1 FROM pg_auth_members WHERE member=r.oid))") == 0 ]] \
        || die 'Existing PostgreSQL role has elevated privileges or memberships; review it manually.'
    if [[ $do_pg_role == skip ]]; then
        [[ $(sql -d postgres -c "SELECT rolcanlogin FROM pg_roles WHERE rolname='fastrag'") == t ]] \
            || die 'Skipped PostgreSQL role cannot log in. Choose overwrite to enable login.'
    fi
fi
if (( pg_db )); then
    [[ $(sql -d postgres -c "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='fastrag'") == "$ACCOUNT" ]] \
        || die 'Existing database is not owned by fastrag. Verify it is dedicated before manually changing the owner.'
    [[ $(sql -d "$DATABASE" -c "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
      WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg_toast%'
        AND c.relkind IN ('r','p','v','m','f') AND (n.nspname<>'public' OR c.relname NOT IN
        ('rag_collections','rag_keys','rag_records','rag_files','rag_chunks','rag_jobs','rag_requests'))") == 0 ]] \
        || die 'Existing database contains non-FastRAG relations; refusing to reuse it.'
fi
dropins=$(systemctl show -p DropInPaths --value "$UNIT_NAME")
[[ -z $dropins ]] || die 'Review/remove existing systemd drop-ins manually before using this installer.'
if [[ $do_unit == skip ]]; then
    fragment=$(systemctl show -p FragmentPath --value "$UNIT_NAME")
    [[ -n $fragment && -f $fragment ]] && cmp -s "$fragment" <(unit_text) \
        || die 'Skipped unit is not the expected pgvector unit. Overwrite it explicitly or manage it manually.'
fi
if ! systemctl is-active --quiet "$UNIT_NAME" && [[ -n $(ss -H -ltn "sport = :$PORT") ]]; then
    die "TCP port $PORT is in use. Free it before installing; no unrelated service will be stopped."
fi

gemini_key=
if ! present "$CONFIG"; then
    printf 'Gemini API key for this installation (hidden): ' >&2
    read -rs gemini_key </dev/tty || die 'Could not read the Gemini API key.'
    printf '\n' >&2
    [[ -n $gemini_key && $gemini_key != CHANGE_ME* && $gemini_key != *[[:space:]]* ]] || die 'Enter a valid Gemini API key.'
fi

backup=
backup_item() {
    local path=$1 name=$2
    if present "$path"; then
        if [[ -z $backup ]]; then
            backup=$(mktemp -d /var/backups/fastrag-system.XXXXXX)
            printf 'Backing up replaced files in %s\n' "$backup"
        fi
        install -d -m 0700 "$(dirname -- "$backup/$name")"
        mv -T -- "$path" "$backup/$name"
    fi
}
trap 'printf "Installation failed at line %s. Review the error and rerun; the database was not dropped.\n" "$LINENO" >&2' ERR

if [[ $do_group == create ]]; then groupadd --system "$ACCOUNT"; fi
if [[ $do_home != skip ]]; then
    install -d -o root -g root -m 0755 "$ROOT"
fi
if [[ $do_os_user == create ]]; then
    useradd --system --gid "$ACCOUNT" --home-dir "$ROOT" --no-create-home --shell /usr/sbin/nologin "$ACCOUNT"
elif [[ $do_os_user == overwrite ]]; then
    if systemctl is-active --quiet "$UNIT_NAME"; then systemctl stop "$UNIT_NAME"; fi
    usermod --gid "$ACCOUNT" --home "$ROOT" --shell /usr/sbin/nologin "$ACCOUNT"
fi
root_dir "$ROOT" || die 'Cannot secure the installation directory.'
if systemctl is-active --quiet "$UNIT_NAME"; then systemctl stop "$UNIT_NAME"; fi
[[ -z $(ss -H -ltn "sport = :$PORT") ]] || die "TCP port $PORT is in use by another service."

if ! present "$ROOT/config"; then install -d -o root -g "$ACCOUNT" -m 0750 "$ROOT/config"; fi
if [[ $do_project != skip ]]; then
    # Stage only runtime/source assets. No user config, caches, environments, logs, or knowledge files.
    stage=$(mktemp -d "$ROOT/.project.XXXXXX")
    trap 'if [[ -n ${stage:-} ]]; then rm -r -- "$stage"; fi' EXIT
    python3 -I - "$SOURCE" "$stage" "${project_items[@]}" <<'PY'
from pathlib import Path
from shutil import copyfile
import os
import sys

src, dest = map(Path, sys.argv[1:3])
allowed = {".py", ".txt", ".sql", ".md", ".yaml", ".sh"}
for item in sys.argv[3:]:
    base = src / item
    if base.is_symlink() or not base.exists():
        continue
    files = [base] if base.is_file() else (
        Path(directory) / name
        for directory, dirs, names in os.walk(base, followlinks=False)
        for name in names if Path(name).suffix in allowed and "__pycache__" not in Path(directory).parts
    )
    for file in files:
        if file.is_symlink() or not file.is_file():
            continue
        output = dest / file.relative_to(src)
        output.parent.mkdir(parents=True, exist_ok=True)
        copyfile(file, output)
        output.chmod(0o755 if output.suffix == ".sh" else 0o644)
for directory, _, _ in os.walk(dest):
    if Path(directory) != dest:
        Path(directory).chmod(0o755)
PY
    for item in "${project_items[@]}"; do
        if present "$stage/$item"; then
            backup_item "$ROOT/$item" "project/$item"
            mv -T -- "$stage/$item" "$ROOT/$item"
        fi
    done
fi

if [[ $do_venv != skip ]]; then
    backup_item "$VENV" venv-fast
    # Build at the final path so pip's executable shebangs remain valid.
    build_venv "$VENV" "$ROOT/app/requirements-pgvector.txt"
fi
if ! present "$CONFIG"; then
    temp_config=$(mktemp "$ROOT/config/.pgvector.XXXXXX")
    printf '%s' "$gemini_key" | python3 -I -c '
import json, sys
print(json.dumps({
    "storage": "pgvector",
    "database": {"dsn": sys.argv[1]},
    "server": {"host": "127.0.0.1", "port": int(sys.argv[2])},
    "gemini": {"api_key": sys.stdin.read()},
}, indent=2))
' "$DSN" "$PORT" >"$temp_config"
    chown "root:$ACCOUNT" "$temp_config"
    chmod 0640 "$temp_config"
    mv -T -- "$temp_config" "$CONFIG"
fi
unset gemini_key

# Verify the existing or generated config targets only the dedicated peer DB.
verify_config "$VENV"
app check-config --config "$CONFIG"

if [[ $do_pg_role == create ]]; then
    sql -d postgres -c 'CREATE ROLE fastrag LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS'
elif [[ $do_pg_role == overwrite ]]; then
    sql -d postgres -c 'ALTER ROLE fastrag LOGIN'
fi
if [[ $do_pg_db == create ]]; then
    sql -d postgres -c 'CREATE DATABASE fastrag OWNER fastrag'
elif [[ $do_pg_db == overwrite ]]; then
    sql -d postgres -c 'GRANT CONNECT ON DATABASE fastrag TO fastrag'
fi
if [[ $do_pg_vector == create ]]; then
    sql -d "$DATABASE" -c 'CREATE EXTENSION vector'
elif [[ $do_pg_vector == overwrite ]]; then
    sql -d "$DATABASE" -c 'ALTER EXTENSION vector UPDATE'
fi
verify_peer
# Idempotent, non-destructive schema setup, also used when reusing a database.
app init-db --config "$CONFIG"
app check --config "$CONFIG"

if ! present "$KEYS"; then
    install -d -o "$ACCOUNT" -g "$ACCOUNT" -m 0700 "$KEYS"
fi
[[ -d $KEYS && ! -L $KEYS && $(stat -c '%U:%a' -- "$KEYS") == "$ACCOUNT:700" ]] \
    || die "$KEYS must be a real directory owned by $ACCOUNT with mode 0700."
if present "$ODOO_KEY"; then
    verify_key_file
    printf 'Keeping existing Odoo API key at %s\n' "$ODOO_KEY"
else
    app create-key --config "$CONFIG" --collection odoo --key-file "$ODOO_KEY"
fi

if [[ $do_unit != skip ]]; then
    backup_item "$UNIT" unit/fastrag.service
    new_unit=$(mktemp -d /run/fastrag-unit.XXXXXX)
    unit_text >"$new_unit/$UNIT_NAME"
    systemd-analyze verify "$new_unit/$UNIT_NAME"
    install -m 0644 "$new_unit/$UNIT_NAME" "$UNIT"
    rm -- "$new_unit/$UNIT_NAME"
    rmdir -- "$new_unit"
fi
systemctl daemon-reload
systemctl enable --now "$UNIT_NAME"
for (( attempt=0; attempt<20; attempt++ )); do
    if systemctl is-active --quiet "$UNIT_NAME" \
        && curl -q --fail --silent --noproxy '*' --max-time 2 "http://127.0.0.1:$PORT/healthz" >/dev/null; then
        printf 'FastRAG is running at http://127.0.0.1:%s\n' "$PORT"
        printf 'Odoo API key file: %s\n' "$ODOO_KEY"
        exit 0
    fi
    sleep 1
done
die 'Service did not become healthy. Check: sudo journalctl -u fastrag.service -n 50'
