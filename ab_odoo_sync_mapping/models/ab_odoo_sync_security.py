import re

from odoo.tools.translate import _


MIN_ROUNDS = 600_000
MAX_ROUNDS = 4_294_967_295
SYNC_KEY_MIN_LENGTH = 32
SYNC_KEY_MAX_LENGTH = 128
HDD_SERIAL_MAX_LENGTH = 128

_PBKDF2_ROUNDS_RE = re.compile(r"^\$pbkdf2-sha512\$(\d+)\$")
_SYNC_KEY_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_PLACEHOLDER_SERIALS = {
    "0",
    "00000000",
    "0000000000000000",
    "none",
    "null",
    "unknown",
    "to be filled by o.e.m.",
    "to be filled by oem",
}


class SyncConfigurationError(Exception):
    pass


def _crypt_context():
    try:
        from passlib.context import CryptContext
    except ImportError as ex:
        raise SyncConfigurationError(
            _("Python package passlib is required for Odoo sync API keys.")
        ) from ex
    return CryptContext(
        ["pbkdf2_sha512"],
        pbkdf2_sha512__rounds=MIN_ROUNDS,
    )


def validate_rounds(rounds):
    try:
        rounds = int(rounds)
    except (TypeError, ValueError) as ex:
        raise ValueError(_("PBKDF2 rounds must be an integer.")) from ex
    if rounds < MIN_ROUNDS or rounds > MAX_ROUNDS:
        raise ValueError(
            _("PBKDF2 rounds must be between 600000 and 4294967295.")
        )
    return rounds


def validate_stored_hash_rounds(stored_hash):
    match = _PBKDF2_ROUNDS_RE.match(stored_hash or "")
    if not match:
        raise ValueError(_("Stored API key hash must use pbkdf2_sha512."))
    validate_rounds(match.group(1))


def hash_sync_key(api_key, rounds=MIN_ROUNDS):
    validate_rounds(rounds)
    return _crypt_context().hash(api_key)


def verify_sync_key(received_key, stored_hash):
    validate_stored_hash_rounds(stored_hash)
    return _crypt_context().verify(received_key, stored_hash)


def validate_sync_key_value(api_key):
    if not isinstance(api_key, str):
        return False
    if api_key != api_key.strip():
        return False
    try:
        api_key.encode("ascii")
    except UnicodeEncodeError:
        return False
    if len(api_key) < SYNC_KEY_MIN_LENGTH or len(api_key) > SYNC_KEY_MAX_LENGTH:
        return False
    return bool(_SYNC_KEY_RE.match(api_key))


def normalize_hdd_serial(serial):
    if not isinstance(serial, str):
        raise ValueError(_("Hardware serial must be a string."))
    serial = serial.strip()
    if not serial:
        raise ValueError(_("Hardware serial is required."))
    if len(serial) > HDD_SERIAL_MAX_LENGTH:
        raise ValueError(_("Hardware serial is too long."))
    if any(ord(character) < 32 or ord(character) == 127 for character in serial):
        raise ValueError(_("Hardware serial must not contain control characters."))
    lowered = serial.lower()
    if lowered.startswith("---") or lowered in _PLACEHOLDER_SERIALS:
        raise ValueError(_("Hardware serial is not stable enough for binding."))
    if set(serial) == {"0"}:
        raise ValueError(_("Hardware serial is not stable enough for binding."))
    return serial
