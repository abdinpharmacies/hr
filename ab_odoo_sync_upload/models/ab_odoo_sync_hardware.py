import json
import re
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


def _natural_device_name_key(device):
    name = str((device or {}).get("name") or "")
    parts = []
    for part in re.split(r"(\d+)", name):
        if not part:
            continue
        if part.isdigit():
            parts.append((0, int(part)))
        else:
            parts.append((1, part.lower()))
    return (parts, name)


def _is_removable_disk(device):
    value = (device or {}).get("rm")
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true"}
    return value is True or value == 1


def _is_eligible_internal_disk(device):
    if not isinstance(device, dict):
        return False
    if device.get("type") != "disk":
        return False
    if _is_removable_disk(device):
        return False
    transport = device.get("tran")
    return not isinstance(transport, str) or transport.strip().lower() != "usb"


def _device_display_name(device):
    return str((device or {}).get("name") or "<unknown>")


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


def read_hdd_serial():
    try:
        result = subprocess.run(
            ["lsblk", "--json", "--nodeps", "--output", "NAME,TYPE,RM,TRAN,SERIAL"],
            timeout=5,
            text=True,
            capture_output=True,
            check=False,
        )
    except subprocess.TimeoutExpired as ex:
        raise ValueError(_("Timed out while reading hardware serial with lsblk.")) from ex
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
    if not isinstance(payload, dict):
        raise ValueError(
            _("lsblk returned invalid disk data while reading hardware serial.")
        )
    devices = payload.get("blockdevices")
    if not isinstance(devices, list):
        raise ValueError(
            _("lsblk returned invalid disk data while reading hardware serial.")
        )
    eligible_devices = sorted(
        (device for device in devices if _is_eligible_internal_disk(device)),
        key=_natural_device_name_key,
    )
    if not eligible_devices:
        raise ValueError(
            _("lsblk did not return any eligible internal disks for hardware serial discovery.")
        )

    selected_device = eligible_devices[0]
    serial = selected_device.get("serial")
    device_name = _device_display_name(selected_device)
    if not serial:
        raise ValueError(
            _("Selected internal disk %(device)s did not report a hardware serial.")
            % {"device": device_name}
        )
    try:
        return normalize_hdd_serial(serial)
    except ValueError as ex:
        raise ValueError(
            _("Selected internal disk %(device)s has an invalid hardware serial: %(error)s")
            % {
                "device": device_name,
                "error": ex,
            }
        ) from ex
