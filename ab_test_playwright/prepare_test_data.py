#!/usr/bin/env python3
"""Label the agreed development fixtures and reset their Odoo login via SQL."""

import argparse
import configparser
import getpass
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone

import psycopg2
from psycopg2 import sql
from passlib.context import CryptContext


TARGETS = {
    "ab_product": [74542, 94123],
    "ab_product_card": [74542, 94123],
    "ab_customer": [19934],
    "ab_promo_program": [2],
    "ab_contract": [1, 2, 3, 4],
    "ab_store": [104],
    "ab_hr_employee": [668],
    "res_partner": [2455],
}


def preparation_database(parser, database):
    if database is None:
        if not sys.stdin.isatty():
            parser.error('Specify --db when running unattended')
        try:
            database = input('Database name: ')
        except EOFError:
            parser.error('Database name is required')
    if not database.strip():
        parser.error('Database name must not be empty')
    return database


def connect(config_path, database):
    config = configparser.RawConfigParser()
    if not config.read(config_path):
        raise ValueError("Cannot read the Odoo config file")
    options = config["options"]
    kwargs = {"dbname": database, "connect_timeout": 10}
    for source, target in (("db_host", "host"), ("db_port", "port"),
                           ("db_user", "user"), ("db_password", "password"),
                           ("db_sslmode", "sslmode")):
        value = options.get(source)
        if value and value.lower() not in {"false", "none"}:
            kwargs[target] = value
    return psycopg2.connect(**kwargs)


def select_rows(cursor, table, columns, ids, lock=False):
    query = sql.SQL("SELECT {} FROM {} WHERE id = ANY(%s) ORDER BY id{}").format(
        sql.SQL(", ").join(map(sql.Identifier, columns)), sql.Identifier(table),
        sql.SQL(" FOR UPDATE" if lock else ""),
    )
    cursor.execute(query, (ids,))
    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    if [row["id"] for row in rows] != sorted(ids):
        raise ValueError(f"Missing or unexpected records in {table}")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(Path(__file__).resolve().parent.parent / "odoo19-POS.conf"))
    parser.add_argument("--db", help="Database name; prompted when omitted")
    parser.add_argument("--apply", action="store_true", help="Apply changes; default is read-only preview")
    parser.add_argument("--password-env", default="AB_TEST_PASSWORD")
    parser.add_argument("--backup-dir", type=Path, default=Path(__file__).resolve().parent / "backups")
    args = parser.parse_args()
    args.db = preparation_database(parser, args.db)
    password = None
    if args.apply:
        password = os.environ.get(args.password_env) or getpass.getpass("New Odoo test password: ")
        if not password:
            raise ValueError("A nonempty password is required")

    conn = connect(args.config, args.db)
    backup_path = None
    try:
        conn.set_session(readonly=not args.apply, isolation_level="SERIALIZABLE")
        with conn.cursor() as cursor:
            cursor.execute("SET LOCAL lock_timeout = '5s'")
            cursor.execute("SET LOCAL statement_timeout = '30s'")
            user = select_rows(cursor, "res_users", ["id", "login", "partner_id", "password", "active"], [2452], args.apply)[0]
            profile = select_rows(cursor, "ab_employee_access", ["id", "employee_id"], [1], args.apply)[0]
            if user["partner_id"] != 2455 or profile["employee_id"] != 668 or not user["active"]:
                raise ValueError("User/employee fixture links changed or login is inactive")
            cursor.execute("SELECT id, product_card_id FROM ab_product WHERE product_card_id = ANY(%s) ORDER BY id", ([74542, 94123],))
            if cursor.fetchall() != [(74542, 74542), (94123, 94123)]:
                raise ValueError("Product cards changed or are shared with other products")

            changes = []
            for table, ids in TARGETS.items():
                for row in select_rows(cursor, table, ["id", "name"], ids, args.apply):
                    name = row["name"] or ""
                    if not isinstance(name, str):
                        raise ValueError(f"Unexpected name column type: {table}")
                    new_name = name if name.startswith("[TEST] ") else "[TEST] " + name
                    changes.append({"table": table, "id": row["id"], "column": "name", "before": row["name"], "after": new_name})
                    print(f"{table} {row['id']}: {new_name}")

            if not args.apply:
                print(f"Preview only. User 2452 login: {user['login']}. No changes made.")
                conn.rollback()
                return

            cursor.execute("SELECT value FROM ir_config_parameter WHERE key = %s", ("password.hashing.rounds",))
            configured = cursor.fetchone()
            rounds = max(600_000, int(configured[0] or 0) if configured else 0)
            crypt = CryptContext(schemes=["pbkdf2_sha512"], pbkdf2_sha512__rounds=rounds)
            hashed = crypt.hash(password)
            assert crypt.verify(password, hashed)
            changes.append({"table": "res_users", "id": 2452, "column": "password", "before": user["password"], "after": hashed})

            args.backup_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            os.chmod(args.backup_dir, 0o700)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            backup_path = args.backup_dir / f"before-test-labels-{stamp}.json"
            descriptor = os.open(backup_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as backup:
                json.dump({"database": args.db, "created_at": stamp, "changes": changes}, backup, ensure_ascii=False, indent=2)
                backup.flush()
                os.fsync(backup.fileno())

            for change in changes:
                if change["before"] == change["after"]:
                    continue
                cursor.execute(sql.SQL("UPDATE {} SET {} = %s WHERE id = %s AND {} IS NOT DISTINCT FROM %s").format(
                    sql.Identifier(change["table"]), sql.Identifier(change["column"]), sql.Identifier(change["column"])),
                    (change["after"], change["id"], change["before"]))
                if cursor.rowcount != 1:
                    raise ValueError(f"Unexpected update count: {change['table']} {change['id']}")

            for change in changes:
                row = select_rows(cursor, change["table"], ["id", change["column"]], [change["id"]])[0]
                if row[change["column"]] != change["after"]:
                    raise ValueError(f"Verification failed: {change['table']} {change['id']}")
            conn.commit()
            print(f"Committed and verified {len(changes) - 1} labels and one password hash.")
            print(f"Owner-only backup: {backup_path}")
            print("Refresh the Odoo server caches before browser verification. Employee PIN is unchanged.")
    except Exception:
        conn.rollback()
        if backup_path:
            print(f"Backup retained at {backup_path}; transaction was not confirmed successful.", file=sys.stderr)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, configparser.Error, psycopg2.Error) as error:
        # Do not expose DSNs, credentials, or SQL parameters in error output.
        print(f"Preparation failed ({type(error).__name__}); no partial transaction is committed.", file=sys.stderr)
        sys.exit(1)
