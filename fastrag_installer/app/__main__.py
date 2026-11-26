import argparse
import asyncio
import os
from pathlib import Path
import re
import secrets
import sys

from .settings import load_settings
from .odoo_client import OdooClient
from .contracts import API_VERSION


def main():
    parser = argparse.ArgumentParser(description="Standalone FastRAG")
    parser.add_argument("command", choices=["serve", "check", "check-config", "init-db", "create-key", "revoke-key"])
    parser.add_argument("--config")
    parser.add_argument("--collection", default="default")
    parser.add_argument("--permissions", default="read,write,query")
    parser.add_argument("--public-only", action="store_true")
    parser.add_argument("--key-file", type=Path, help="Private file to create or read; never pass a raw key")
    args = parser.parse_args()
    admin = args.command in {"init-db", "create-key", "revoke-key"}
    try:
        cfg = load_settings(args.config)
        if admin:
            cfg.require_database()
        else:
            cfg.require_credentials()
    except Exception as exc:
        # ValidationError values may contain secrets. Report only the class.
        print(f"Configuration invalid ({type(exc).__name__}); check config/config.yaml and required keys", file=sys.stderr)
        return 1
    if args.command == "check-config":
        print("Configuration is valid (credentials have not been checked remotely).")
        return 0
    if cfg.storage == "pgvector" and (admin or args.command == "check"):
        return pg_admin(cfg, args, parser)
    if args.command == "check":
        async def check():
            client = OdooClient(cfg.odoo)
            try:
                await client.check(cfg.gemini)
            finally:
                await client.close()
        try:
            asyncio.run(check())
        except Exception as exc:
            print(f"Odoo readiness failed ({type(exc).__name__}); verify API key, addon, database, pgvector and model settings", file=sys.stderr)
            return 1
        print(f"Odoo API v{API_VERSION}, permissions, pgvector, and embedding settings are ready.")
        return 0
    import uvicorn
    if cfg.storage == "pgvector":
        from .pg_api import create_app
        server_options = {"limit_concurrency": 64, "timeout_keep_alive": 10, "access_log": False}
    else:
        from .main import create_app
        server_options = {}
    uvicorn.run(create_app(cfg), host=cfg.server.host, port=cfg.server.port, workers=1,
                proxy_headers=False, **server_options)
    return 0


def pg_admin(cfg, args, parser):
    from .pg_store import Store, digest

    permissions = sorted(set(args.permissions.split(",")))
    if args.command in {"create-key", "revoke-key"} and args.key_file is None:
        parser.error("--key-file is required")
    if args.command == "create-key":
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", args.collection):
            parser.error("Invalid collection name")
        if not set(permissions) <= {"read", "write", "query"} or args.public_only and permissions != ["query"]:
            parser.error("Invalid permissions; --public-only requires --permissions query")

    async def run():
        store = Store(cfg.database.dsn.get_secret_value())
        await store.pool.open()
        try:
            if args.command == "init-db":
                await store.migrate()
                print("FastRAG database initialized.")
            elif args.command == "create-key":
                key = secrets.token_urlsafe(32)
                fd = os.open(args.key_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                try:
                    with os.fdopen(fd, "w") as output:
                        output.write(key + "\n")
                    await store.add_key(args.collection, digest(key), permissions, args.public_only)
                except BaseException:
                    args.key_file.unlink(missing_ok=True)
                    raise
                print("API key written to the requested private file.")
            elif args.command == "revoke-key":
                key = args.key_file.read_text(encoding="ascii").strip()
                if not await store.revoke_key(digest(key)):
                    print("No active matching API key found.", file=sys.stderr)
                    return 1
                print("API key revoked; existing cache entries expire within five seconds.")
            else:
                await store.ready()
                print("FastRAG database and pgvector are ready.")
            return 0
        finally:
            await store.pool.close()

    try:
        return asyncio.run(run())
    except Exception as exc:
        print(f"FastRAG database command failed ({type(exc).__name__}); check database, pgvector and permissions",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
