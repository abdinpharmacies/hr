import argparse
import os
from pathlib import Path
import secrets


def main():
    parser = argparse.ArgumentParser(description="Provision the storefront Telegram webhook secret.")
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    args.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if args.directory.stat().st_mode & 0o077:
        parser.error("The secret directory must have mode 0700.")
    values = {"telegram_webhook_secret": secrets.token_urlsafe(32)}
    for name, value in values.items():
        path = args.directory / name
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            stream.write(value)
    print("Webhook secret file created with mode 0600. Set the bot token in the ab_storefront_auth.telegram_bot_token system parameter.")


if __name__ == "__main__":
    main()
