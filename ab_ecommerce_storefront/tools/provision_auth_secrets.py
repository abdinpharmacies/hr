import argparse
import getpass
import os
from pathlib import Path
import re
import secrets


def main():
    parser = argparse.ArgumentParser(description="Provision storefront Telegram secrets without command-line credentials.")
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    args.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if args.directory.stat().st_mode & 0o077:
        parser.error("The secret directory must have mode 0700.")
    token = getpass.getpass("Existing Telegram bot token (hidden): ").strip()
    if not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]{20,}", token):
        parser.error("Invalid bot-token format.")
    values = {"telegram_token": token, "telegram_webhook_secret": secrets.token_urlsafe(32)}
    for name, value in values.items():
        path = args.directory / name
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            stream.write(value)
    print("Secret files created with mode 0600. Configure the Odoo service to read these paths.")


if __name__ == "__main__":
    main()
