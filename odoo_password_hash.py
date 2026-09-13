#!/usr/bin/env python3
"""Generate a one-way password hash using Odoo 19's standard settings.

Run inside a Python virtual environment with Passlib installed:
    python -m pip install passlib==1.7.4
    python z_tools/odoo_password_hash.py
    python z_tools/odoo_password_hash.py --rounds 800000

Input is hidden and preserved exactly, including whitespace and Unicode.
Only the resulting hash is printed to stdout. Each run uses a random salt.
This script does not connect to Odoo or change any user's password.
The default matches Odoo's 600,000 rounds; use --rounds to match a higher
password.hashing.rounds setting. Custom Odoo hashing overrides are not used.
"""

import argparse
import getpass
import sys
import warnings


MIN_ROUNDS = 600_000


def parse_rounds(value: str) -> int:
    """Validate the Odoo minimum and PBKDF2's supported upper bound."""
    try:
        rounds = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("Rounds must be an integer.") from None
    if not MIN_ROUNDS <= rounds <= 4_294_967_295:
        raise argparse.ArgumentTypeError(
            "Rounds must be between 600000 and 4294967295."
        )
    return rounds


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rounds", type=parse_rounds, default=MIN_ROUNDS,
        help="PBKDF2-SHA512 iterations (default: 600000).",
    )
    args = parser.parse_args()

    try:
        from passlib.context import CryptContext
    except ImportError:
        print(
            "Install Passlib in your virtual environment: "
            "python -m pip install passlib==1.7.4",
            file=sys.stderr,
        )
        return 1

    try:
        with warnings.catch_warnings():
            # Refuse getpass's visible-input fallback if no terminal is available.
            warnings.simplefilter("error", getpass.GetPassWarning)
            text = getpass.getpass("Enter text to hash: ")
        if not text:
            print("Error: text must not be empty.", file=sys.stderr)
            return 1
        context = CryptContext(
            ["pbkdf2_sha512"], pbkdf2_sha512__rounds=args.rounds,
        )
        hashed = context.hash(text)
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.", file=sys.stderr)
        return 1
    except getpass.GetPassWarning:
        print("Error: run this script in an interactive terminal.", file=sys.stderr)
        return 1
    except ValueError:
        print("Error: text exceeds the password hasher's supported limits.", file=sys.stderr)
        return 1

    print(hashed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
