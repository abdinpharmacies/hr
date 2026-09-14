import json
import subprocess

from odoo.tools.translate import _


HDD_SERIAL_MAX_LENGTH = 128
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


def validate_hdd_device_path(device_path):
    device_path = (device_path or "").strip()
    if not device_path:
        raise ValueError(
            _("Set the hardware device path system parameter: ab_odoo_sync.hdd_device_path")
        )
    if not device_path.startswith("/dev/disk/by-id/"):
        raise ValueError(
            _("Hardware device path must use a stable /dev/disk/by-id/... path.")
        )
    if any(ord(character) < 32 or ord(character) == 127 for character in device_path):
        raise ValueError(_("Hardware device path must not contain control characters."))
    return device_path


def read_hdd_serial(device_path):
    device_path = validate_hdd_device_path(device_path)
    try:
        result = subprocess.run(
            ["lsblk", "--json", "--output", "SERIAL", device_path],
            timeout=5,
            text=True,
            capture_output=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as ex:
        raise ValueError(_("Could not read hardware serial: %s") % ex) from ex
    if result.returncode:
        raise ValueError(
            _("Could not read hardware serial with lsblk: %s")
            % (result.stderr or result.stdout or result.returncode)
        )
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as ex:
        raise ValueError(_("lsblk returned invalid JSON while reading hardware serial.")) from ex
    for device in payload.get("blockdevices") or []:
        serial = device.get("serial")
        if serial:
            return normalize_hdd_serial(serial)
    raise ValueError(_("lsblk did not return a hardware serial for the configured device."))
