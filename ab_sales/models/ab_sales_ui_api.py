# -*- coding: utf-8 -*-

import os
import shutil
import subprocess
import tempfile
import ipaddress
import socket
import json
import re
from pathlib import Path
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.misc import find_in_path


class AbSalesUiApi(models.TransientModel):
    _name = "ab_sales_ui_api"
    _description = "Sales UI API"

    create_date = fields.Datetime(readonly=True)
    _POS_PRINTER_PARAM = "ab_sales.pos_printer_name"
    _POS_RECEIPT_HEADER_PARAM = "ab_sales.pos_receipt_header"
    _POS_RECEIPT_FOOTER_PARAM = "ab_sales.pos_receipt_footer"
    _POS_UI_SETTINGS_DEFAULTS = {
        "productHasBalanceOnly": True,
        "productHasPosBalanceOnly": True,
        "bill_wizard_printer_id": 0,
        "bill_wizard_printer_name": "",
        "bill_wizard_print_format": "a4",
    }

    @api.model
    def _find_required_binary(self, binary_name):
        try:
            return find_in_path(binary_name)
        except IOError:
            raise UserError(_("Direct print is not available on this server (missing '%s').") % binary_name)

    @api.model
    def get_printer_settings(self):
        config = self.env["ir.config_parameter"].sudo()
        header = config.get_param(self._POS_RECEIPT_HEADER_PARAM)
        footer = config.get_param(self._POS_RECEIPT_FOOTER_PARAM)
        if header is None:
            header = "Sales Receipt"
        if footer is None:
            footer = "Thank you."
        return {
            "printer_name": config.get_param(self._POS_PRINTER_PARAM, "") or "",
            "receipt_header": header,
            "receipt_footer": footer,
        }

    @api.model
    def set_printer_settings(self, printer_name=None, receipt_header=None, receipt_footer=None):
        name = (printer_name or "").strip()
        config = self.env["ir.config_parameter"].sudo()
        config.set_param(self._POS_PRINTER_PARAM, name)
        if receipt_header is not None:
            config.set_param(self._POS_RECEIPT_HEADER_PARAM, (receipt_header or "").strip())
        if receipt_footer is not None:
            config.set_param(self._POS_RECEIPT_FOOTER_PARAM, (receipt_footer or "").strip())
        return self.get_printer_settings()

    @api.model
    def _list_available_printer_names(self):
        names = []

        if os.name == "nt":
            try:
                import win32print  # type: ignore

                flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
                for row in win32print.EnumPrinters(flags):
                    name = row[2] if len(row) > 2 else ""
                    if name:
                        names.append(str(name).strip())
            except Exception:
                try:
                    result = subprocess.run(
                        [
                            "powershell",
                            "-NoProfile",
                            "-Command",
                            "Get-Printer | Select-Object -ExpandProperty Name",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=5,
                        check=False,
                    )
                    if result.returncode == 0:
                        for line in (result.stdout or "").splitlines():
                            name = (line or "").strip()
                            if name:
                                names.append(name)
                except Exception:
                    pass
        else:
            try:
                if shutil.which("lpstat"):
                    result = subprocess.run(
                        ["lpstat", "-a"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                        check=False,
                    )
                    if result.returncode == 0:
                        for line in (result.stdout or "").splitlines():
                            text = (line or "").strip()
                            if not text:
                                continue
                            name = text.split()[0]
                            if name:
                                names.append(name)
            except Exception:
                pass

        return self._bill_wizard_normalize_printer_names(names)

    @api.model
    def _bill_wizard_normalize_printer_names(self, names):
        if isinstance(names, str):
            names = [names]
        elif not isinstance(names, (list, tuple, set)):
            names = [names] if names else []
        seen = set()
        unique = []
        for name in names:
            normalized = str(name or "").strip()
            if not normalized:
                continue
            key = normalized.casefold()
            if key in seen:
                continue
            seen.add(key)
            unique.append(normalized)
        unique.sort(key=lambda n: n.casefold())
        return unique

    @api.model
    def _bill_wizard_expand_ip_range(self, start_ip, end_ip, max_hosts=256):
        try:
            start_addr = ipaddress.ip_address(str(start_ip or "").strip())
            end_addr = ipaddress.ip_address(str(end_ip or "").strip())
        except ValueError:
            raise UserError(_("Invalid IP range."))
        if start_addr.version != 4 or end_addr.version != 4:
            raise UserError(_("Only IPv4 ranges are supported."))
        start_int = int(start_addr)
        end_int = int(end_addr)
        if end_int < start_int:
            start_int, end_int = end_int, start_int
        count = end_int - start_int + 1
        if count > int(max_hosts or 256):
            raise UserError(_("IP range is too large. Maximum is %s addresses.") % int(max_hosts or 256))
        return [str(ipaddress.IPv4Address(num)) for num in range(start_int, end_int + 1)]

    @api.model
    def _bill_wizard_windows_discover_and_install_shared(self, start_ip, end_ip):
        script = r"""
$start=$env:AB_SCAN_START
$end=$env:AB_SCAN_END
function IpToInt($ip) {
  $parts = $ip.Split('.')
  if ($parts.Count -ne 4) { return 0 }
  return ([int]$parts[0] -shl 24) -bor ([int]$parts[1] -shl 16) -bor ([int]$parts[2] -shl 8) -bor [int]$parts[3]
}
function IntToIp($intValue) {
  $a = ($intValue -shr 24) -band 255
  $b = ($intValue -shr 16) -band 255
  $c = ($intValue -shr 8) -band 255
  $d = $intValue -band 255
  return "$a.$b.$c.$d"
}
$discovered = New-Object System.Collections.Generic.List[string]
$installed = New-Object System.Collections.Generic.List[string]
$existing = @{}
try {
  Get-Printer -ErrorAction SilentlyContinue | ForEach-Object {
    $name = [string]$_.Name
    if (-not [string]::IsNullOrWhiteSpace($name)) { $existing[$name.ToLowerInvariant()] = $true }
  }
} catch {}
$startInt = IpToInt $start
$endInt = IpToInt $end
if ($endInt -lt $startInt) {
  $tmp = $startInt
  $startInt = $endInt
  $endInt = $tmp
}
for ($i = $startInt; $i -le $endInt; $i++) {
  $ip = IntToIp $i
  $rows = @()
  try {
    $rows = Get-CimInstance Win32_Printer -ComputerName $ip -ErrorAction Stop |
      Where-Object { $_.Shared -and -not [string]::IsNullOrWhiteSpace($_.ShareName) }
  } catch {}
  foreach ($row in $rows) {
    $share = [string]$row.ShareName
    if ([string]::IsNullOrWhiteSpace($share)) { continue }
    $conn = "\\{0}\{1}" -f $ip, $share
    if (-not $discovered.Contains($conn)) { $discovered.Add($conn) }
    $key = $conn.ToLowerInvariant()
    if (-not $existing.ContainsKey($key)) {
      try {
        Add-Printer -ConnectionName $conn -ErrorAction Stop | Out-Null
        $existing[$key] = $true
        if (-not $installed.Contains($conn)) { $installed.Add($conn) }
      } catch {}
    }
  }
}
@{
  discovered = @($discovered)
  installed = @($installed)
} | ConvertTo-Json -Compress -Depth 5
"""
        env = os.environ.copy()
        env["AB_SCAN_START"] = str(start_ip or "").strip()
        env["AB_SCAN_END"] = str(end_ip or "").strip()
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            timeout=180,
            check=False,
        )
        if result.returncode != 0:
            err = (result.stderr or result.stdout or "").strip()
            raise UserError(_("Printer discovery failed: %s") % (err or _("PowerShell command failed.")))
        payload = {}
        try:
            payload = json.loads((result.stdout or "").strip() or "{}")
        except Exception:
            payload = {}
        discovered = self._bill_wizard_normalize_printer_names(payload.get("discovered") or [])
        installed = self._bill_wizard_normalize_printer_names(payload.get("installed") or [])
        return discovered, installed

    @api.model
    def _bill_wizard_linux_printer_exists(self, queue_name):
        if not shutil.which("lpstat"):
            return False
        result = subprocess.run(
            ["lpstat", "-p", str(queue_name or "").strip()],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return result.returncode == 0

    @api.model
    def _bill_wizard_port_open(self, ip_text, port, timeout=0.35):
        try:
            with socket.create_connection((str(ip_text or "").strip(), int(port)), timeout=float(timeout or 0.35)):
                return True
        except Exception:
            return False

    @api.model
    def _bill_wizard_linux_install_queue(self, queue_name, device_uri, model_name):
        if self._bill_wizard_linux_printer_exists(queue_name):
            return False
        result = subprocess.run(
            ["lpadmin", "-p", queue_name, "-E", "-v", device_uri, "-m", model_name],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if result.returncode != 0:
            return False
        return True

    @api.model
    def _bill_wizard_linux_safe_queue_name(self, prefix, ip_text, suffix=""):
        raw = f"{prefix}_{str(ip_text or '').replace('.', '_')}_{str(suffix or '')}"
        clean = re.sub(r"[^A-Za-z0-9_]+", "_", raw).strip("_")
        return clean[:60] if clean else f"{prefix}_queue"

    @api.model
    def _bill_wizard_linux_smb_printer_shares(self, ip_text):
        if not shutil.which("smbclient"):
            return []
        target = f"//{str(ip_text or '').strip()}"
        result = subprocess.run(
            ["smbclient", "-N", "-L", target],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        if result.returncode != 0:
            return []
        shares = []
        for line in (result.stdout or "").splitlines():
            text = str(line or "").rstrip()
            if not text:
                continue
            parts = re.split(r"\s{2,}", text.strip())
            if len(parts) < 2:
                continue
            share_name = str(parts[0] or "").strip()
            share_type = str(parts[1] or "").strip().lower()
            if share_name and "printer" in share_type:
                shares.append(share_name)
        return self._bill_wizard_normalize_printer_names(shares)

    @api.model
    def _bill_wizard_linux_discover_and_install_shared(self, ip_list):
        if not shutil.which("lpadmin"):
            raise UserError(_("Printer discovery is not available on this server (missing lpadmin)."))
        discovered = []
        installed = []
        for ip_text in ip_list:
            safe_ip = str(ip_text or "").strip()
            if not safe_ip:
                continue
            queue_suffix = safe_ip.replace(".", "_")
            smb_shares = self._bill_wizard_linux_smb_printer_shares(safe_ip)
            for share in smb_shares:
                queue = self._bill_wizard_linux_safe_queue_name("NET_SMB", safe_ip, share)
                discovered.append(queue)
                if self._bill_wizard_linux_install_queue(queue, f"smb://{safe_ip}/{share}", "raw"):
                    installed.append(queue)
            if self._bill_wizard_port_open(safe_ip, 631):
                queue = f"NET_IPP_{queue_suffix}"
                discovered.append(queue)
                if self._bill_wizard_linux_install_queue(queue, f"ipp://{safe_ip}/ipp/print", "everywhere"):
                    installed.append(queue)
                continue
            if self._bill_wizard_port_open(safe_ip, 9100):
                queue = f"NET_RAW_{queue_suffix}"
                discovered.append(queue)
                if self._bill_wizard_linux_install_queue(queue, f"socket://{safe_ip}:9100", "raw"):
                    installed.append(queue)
        return (
            self._bill_wizard_normalize_printer_names(discovered),
            self._bill_wizard_normalize_printer_names(installed),
        )

    @api.model
    def bill_wizard_discover_shared_printers(self, start_ip="", end_ip=""):
        ip_list = self._bill_wizard_expand_ip_range(start_ip, end_ip, max_hosts=256)
        if os.name == "nt":
            discovered, installed = self._bill_wizard_windows_discover_and_install_shared(start_ip, end_ip)
        else:
            discovered, installed = self._bill_wizard_linux_discover_and_install_shared(ip_list)
        return {
            "ok": True,
            "discovered_count": len(discovered),
            "installed_count": len(installed),
            "discovered_printers": discovered,
            "installed_printers": installed,
            "available_printers": self._list_available_printer_names(),
        }

    @api.model
    def bill_wizard_get_print_options(self):
        settings = self.get_printer_settings()
        user_settings = self._bill_wizard_get_user_print_preferences()
        printers = self.env["ab_printer"].sudo().get_active_printers()
        selected_printer = self._bill_wizard_resolve_selected_printer(
            printer_id=user_settings.get("printer_id"),
            printer_name=user_settings.get("printer_name"),
            print_format=user_settings.get("print_format"),
        )
        selected_name = selected_printer.build_display_label() if selected_printer else (
            user_settings.get("printer_name") or settings.get("printer_name") or ""
        )
        selected_format = (
            selected_printer.paper_size if selected_printer and selected_printer.paper_size in ("pos_80mm", "a4")
            else user_settings.get("print_format")
        ) or "a4"
        return {
            "printer_id": selected_printer.id if selected_printer else 0,
            "printer_name": selected_name,
            "print_format": "pos_80mm" if selected_format == "pos_80mm" else "a4",
            "receipt_header": settings.get("receipt_header") or "Sales Receipt",
            "receipt_footer": settings.get("receipt_footer") or "Thank you.",
            "available_printers": [rec.build_display_label() for rec in printers],
            "available_printer_records": printers.to_print_payload(),
            "default_printer_id": selected_printer.id if selected_printer else 0,
        }

    @api.model
    def _bill_wizard_get_user_print_preferences(self):
        self._require_models("ab_sales_pos_settings")
        settings_model = self.env["ab_sales_pos_settings"].sudo()
        record = settings_model.search([("user_id", "=", self.env.uid)], limit=1)
        payload = self._normalize_pos_ui_settings(record.settings_json if record else {})
        print_format = "pos_80mm" if payload.get("bill_wizard_print_format") == "pos_80mm" else "a4"
        printer_name = str(payload.get("bill_wizard_printer_name") or "").strip()
        try:
            printer_id = int(payload.get("bill_wizard_printer_id") or 0)
        except Exception:
            printer_id = 0

        return {
            "printer_id": printer_id,
            "printer_name": printer_name,
            "print_format": print_format,
        }

    @api.model
    def _bill_wizard_resolve_selected_printer(self, printer_id=0, printer_name="", print_format="a4", allow_fallback=True):
        Printer = self.env["ab_printer"].sudo()
        try:
            printer_id_int = int(printer_id or 0)
        except Exception:
            printer_id_int = 0
        selected = Printer.browse(printer_id_int).exists()
        if selected and selected.active:
            return selected
        if printer_name:
            name_lower = str(printer_name or "").strip().lower()
            active = Printer.get_active_printers()
            matched = active.filtered(lambda p: p.build_display_label().lower() == name_lower)
            if matched:
                return matched[:1]
        if not allow_fallback:
            return Printer
        preferred_size = "pos_80mm" if str(print_format or "").strip() == "pos_80mm" else "a4"
        return Printer.get_default_printer(preferred_size) or Printer.get_default_printer()

    @api.model
    def bill_wizard_set_print_preferences(self, printer_name="", print_format="a4", printer_id=0):
        self._require_models("ab_sales_pos_settings")
        settings_model = self.env["ab_sales_pos_settings"].sudo()
        record = settings_model.search([("user_id", "=", self.env.uid)], limit=1)
        normalized = self._normalize_pos_ui_settings(record.settings_json if record else {})
        try:
            printer_id_int = int(printer_id or 0)
        except Exception:
            printer_id_int = 0
        has_explicit_printer = bool(printer_id_int or str(printer_name or "").strip())
        selected_printer = self._bill_wizard_resolve_selected_printer(
            printer_id=printer_id_int,
            printer_name=printer_name,
            print_format=print_format,
            allow_fallback=has_explicit_printer,
        )
        normalized["bill_wizard_printer_id"] = selected_printer.id if selected_printer else 0
        normalized["bill_wizard_printer_name"] = (
            selected_printer.build_display_label() if selected_printer else str(printer_name or "").strip()
        )
        normalized["bill_wizard_print_format"] = (
            selected_printer.paper_size if selected_printer and selected_printer.paper_size in ("pos_80mm", "a4")
            else ("pos_80mm" if str(print_format or "").strip() == "pos_80mm" else "a4")
        )
        now = fields.Datetime.now()
        if record:
            record.write(
                {
                    "settings_json": normalized,
                    "last_synced_at": now,
                }
            )
        else:
            record = settings_model.create(
                {
                    "user_id": self.env.uid,
                    "settings_version": 1,
                    "last_synced_at": now,
                    "settings_json": normalized,
                }
            )
        return {
            "printer_id": normalized["bill_wizard_printer_id"],
            "printer_name": normalized["bill_wizard_printer_name"],
            "print_format": normalized["bill_wizard_print_format"],
        }

    @api.model
    def _direct_print_text(self, text_content, printer_name=""):
        content = str(text_content or "").strip()
        if not content:
            raise UserError(_("Nothing to print."))

        printer_name = str(printer_name or "").strip()
        if os.name == "nt":
            ps_script = (
                "[Console]::InputEncoding = [System.Text.Encoding]::UTF8; "
                "$printer=$env:AB_PRINT_PRINTER; "
                "$content=[Console]::In.ReadToEnd(); "
                "if ([string]::IsNullOrWhiteSpace($content)) { throw 'Nothing to print.' }; "
                "if ([string]::IsNullOrWhiteSpace($printer)) { "
                "  $content | Out-Printer "
                "} else { "
                "  $content | Out-Printer -Name $printer "
                "}"
            )
            env = os.environ.copy()
            env["AB_PRINT_PRINTER"] = printer_name
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    ps_script,
                ],
                input=content + "\n",
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
                timeout=25,
                check=False,
            )
            if result.returncode != 0:
                err = (result.stderr or result.stdout or "").strip()
                raise UserError(_("Direct print failed: %s") % (err or _("PowerShell print command failed.")))
        else:
            if not shutil.which("lp"):
                raise UserError(_("Direct print is not available on this server (missing 'lp')."))
            cmd = ["lp"]
            if printer_name:
                cmd.extend(["-d", printer_name])

            # thermal_slk fallback uses CP1256 bytes. Keep UTF-8 for other printers.
            encoding_name = "cp1256" if printer_name.lower() == "thermal_slk" else "utf-8"
            payload = (content + "\n").encode(encoding_name, errors="replace")
            result = subprocess.run(
                cmd,
                input=payload,
                capture_output=True,
                text=False,
                timeout=25,
                check=False,
            )
            if result.returncode != 0:
                err_bytes = result.stderr or result.stdout or b""
                err = err_bytes.decode("utf-8", errors="replace").strip()
                raise UserError(_("Direct print failed: %s") % (err or _("lp command failed.")))

        return {"ok": True}

    @api.model
    def _direct_print_linux_escpos_bin(self, html_content, printer_name=""):
        if os.name == "nt":
            raise UserError(_("ESC/POS binary print is only supported on Linux servers."))

        content = str(html_content or "").strip()
        if not content:
            raise UserError(_("Nothing to print."))

        wkhtmltoimage_bin = self._find_required_binary("wkhtmltoimage")
        lp_bin = self._find_required_binary("lp")

        try:
            from escpos.printer import File as EscposFile  # type: ignore
        except Exception as exc:
            raise UserError(_(
                "Python package 'python-escpos' is required for ESC/POS binary printing: %s"
            ) % str(exc))
        try:
            from PIL import Image, ImageChops, ImageOps  # type: ignore
        except Exception as exc:
            raise UserError(_("Python package 'Pillow' is required for POS image processing: %s") % str(exc))

        with tempfile.TemporaryDirectory(prefix="odoo_print_bin_") as tmpdir:
            workdir = Path(tmpdir)
            html_file = workdir / "receipt.html"
            raw_png = workdir / "receipt-raw.png"
            final_png = workdir / "receipt-final.png"
            escpos_bin = workdir / "receipt-print.bin"

            html_file.write_text(content, encoding="utf-8")

            image_result = subprocess.run(
                [
                    wkhtmltoimage_bin,
                    "--encoding",
                    "utf-8",
                    "--format",
                    "png",
                    "--quality",
                    "100",
                    "--enable-local-file-access",
                    "--width",
                    "512",
                    str(html_file),
                    str(raw_png),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=60,
                check=False,
            )
            if image_result.returncode != 0:
                err = (image_result.stderr or image_result.stdout or "").strip()
                raise UserError(_("Direct print failed: %s") % (err or _("wkhtmltoimage command failed.")))

            if not raw_png.exists():
                raise UserError(_("Direct print failed: receipt image was not generated."))

            try:
                side_padding_px = 0
                extra_bottom_px = 24

                with Image.open(raw_png) as image:
                    image = image.convert("RGB")
                    white_bg = Image.new("RGB", image.size, "white")
                    diff = ImageChops.difference(image, white_bg)
                    bbox = diff.getbbox()
                    if bbox:
                        _left, top, _right, bottom = bbox
                        image = image.crop((0, top, image.width, bottom))
                    image = ImageOps.expand(
                        image,
                        border=(side_padding_px, 0, side_padding_px, extra_bottom_px),
                        fill="white",
                    )
                    image.save(final_png, format="PNG")
            except Exception as exc:
                raise UserError(_("Direct print failed while processing POS image: %s") % str(exc))

            try:
                printer = EscposFile(str(escpos_bin))
                printer.image(str(final_png))
                printer.cut()
                printer.close()
            except Exception as exc:
                raise UserError(_("Direct print failed while building ESC/POS binary: %s") % str(exc))

            lp_cmd = [lp_bin]
            selected_printer = str(printer_name or "").strip()
            if selected_printer:
                lp_cmd.extend(["-d", selected_printer])
            lp_cmd.append(str(escpos_bin))
            lp_result = subprocess.run(
                lp_cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=40,
                check=False,
            )
            if lp_result.returncode != 0:
                err = (lp_result.stderr or lp_result.stdout or "").strip()
                raise UserError(_("Direct print failed: %s") % (err or _("lp command failed.")))

        return {"ok": True}

    @api.model
    def _direct_print_html(self, html_content, printer_name="", print_format="a4"):
        content = str(html_content or "").strip()
        if not content:
            raise UserError(_("Nothing to print."))

        printer_name = str(printer_name or "").strip()
        if os.name != "nt":
            fmt = "pos_80mm" if str(print_format or "").strip() == "pos_80mm" else "a4"
            if fmt == "pos_80mm":
                return self._direct_print_linux_escpos_bin(
                    content,
                    printer_name=printer_name,
                )

            if not shutil.which("wkhtmltopdf"):
                raise UserError(_("HTML direct print is not available on this server (missing 'wkhtmltopdf')."))
            if not shutil.which("lp"):
                raise UserError(_("Direct print is not available on this server (missing 'lp')."))
            if printer_name:
                queue_info = subprocess.run(
                    ["lpoptions", "-p", printer_name],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=10,
                    check=False,
                )
                queue_text = (queue_info.stdout or "") + "\n" + (queue_info.stderr or "")
                if "local raw printer" in queue_text.lower():
                    raise UserError(_(
                        "Printer '%s' is a raw queue. HTML/PDF print is blocked to avoid binary garbage output. "
                        "Use text print or configure a non-raw driver queue."
                    ) % printer_name)

            temp_html_path = ""
            temp_pdf_path = ""
            try:
                with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as temp_html:
                    temp_html.write(content)
                    temp_html_path = temp_html.name
                fd, temp_pdf_path = tempfile.mkstemp(suffix=".pdf")
                os.close(fd)

                pdf_result = subprocess.run(
                    [
                        "wkhtmltopdf",
                        "--encoding",
                        "utf-8",
                        "--quiet",
                        temp_html_path,
                        temp_pdf_path,
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=60,
                    check=False,
                )
                if pdf_result.returncode != 0:
                    err = (pdf_result.stderr or pdf_result.stdout or "").strip()
                    raise UserError(_("Direct print failed: %s") % (err or _("wkhtmltopdf command failed.")))

                lp_cmd = ["lp"]
                if printer_name:
                    lp_cmd.extend(["-d", printer_name])
                lp_cmd.append(temp_pdf_path)
                lp_result = subprocess.run(
                    lp_cmd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=40,
                    check=False,
                )
                if lp_result.returncode != 0:
                    err = (lp_result.stderr or lp_result.stdout or "").strip()
                    raise UserError(_("Direct print failed: %s") % (err or _("lp command failed.")))
            finally:
                if temp_html_path and os.path.exists(temp_html_path):
                    try:
                        os.unlink(temp_html_path)
                    except Exception:
                        pass
                if temp_pdf_path and os.path.exists(temp_pdf_path):
                    try:
                        os.unlink(temp_pdf_path)
                    except Exception:
                        pass
            return {"ok": True}

        temp_path = ""
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as temp_file:
                temp_file.write(content)
                temp_path = temp_file.name

            ps_script = (
                "$printer=$env:AB_PRINT_PRINTER; "
                "$path=$env:AB_PRINT_HTML; "
                "if ([string]::IsNullOrWhiteSpace($path) -or -not (Test-Path -LiteralPath $path)) { throw 'Print file not found.' }; "
                "$oldDefault=''; "
                "$network=$null; "
                "$pageSetupKey='HKCU:\\Software\\Microsoft\\Internet Explorer\\PageSetup'; "
                "$oldHeader=$null; "
                "$oldFooter=$null; "
                "try { "
                "  if (Test-Path -LiteralPath $pageSetupKey) { "
                "    $pageSetup = Get-ItemProperty -Path $pageSetupKey -ErrorAction SilentlyContinue; "
                "    $oldHeader = $pageSetup.header; "
                "    $oldFooter = $pageSetup.footer; "
                "    Set-ItemProperty -Path $pageSetupKey -Name header -Value ''; "
                "    Set-ItemProperty -Path $pageSetupKey -Name footer -Value ''; "
                "  }; "
                "  if (-not [string]::IsNullOrWhiteSpace($printer)) { "
                "    $current = Get-CimInstance Win32_Printer -Filter \"Default=True\" | Select-Object -First 1; "
                "    if ($current) { $oldDefault = $current.Name }; "
                "    $network = New-Object -ComObject WScript.Network; "
                "    $network.SetDefaultPrinter($printer); "
                "  }; "
                "  Add-Type -AssemblyName System.Windows.Forms; "
                "  $script:printed = $false; "
                "  $script:printErr = ''; "
                "  $isVirtual = $false; "
                "  if (-not [string]::IsNullOrWhiteSpace($printer)) { "
                "    $pn = $printer.ToLowerInvariant(); "
                "    if ($pn.Contains('pdf') -or $pn.Contains('xps') -or $pn.Contains('onenote') -or $pn.Contains('fax')) { "
                "      $isVirtual = $true; "
                "    } "
                "  }; "
                "  $browser = New-Object System.Windows.Forms.WebBrowser; "
                "  $browser.ScriptErrorsSuppressed = $true; "
                "  $handler = [System.Windows.Forms.WebBrowserDocumentCompletedEventHandler]{ "
                "    param($sender,$args) "
                "    if ($sender.ReadyState -eq [System.Windows.Forms.WebBrowserReadyState]::Complete -and -not $script:printed) { "
                "      try { "
                "        Start-Sleep -Milliseconds 300; "
                "        if ($isVirtual) { "
                "          $ok = $sender.ShowPrintDialog(); "
                "          if (-not $ok) { $script:printErr = 'Print canceled.' } "
                "        } else { "
                "          $sender.Print(); "
                "        } "
                "      } catch { "
                "        $script:printErr = $_.Exception.Message; "
                "      } finally { "
                "        $script:printed = $true; "
                "      } "
                "    } "
                "  }; "
                "  $browser.add_DocumentCompleted($handler); "
                "  $uri = [System.Uri]::new($path).AbsoluteUri; "
                "  $browser.Navigate($uri); "
                "  $sw = [System.Diagnostics.Stopwatch]::StartNew(); "
                "  while (-not $script:printed -and $sw.Elapsed.TotalSeconds -lt 20) { "
                "    [System.Windows.Forms.Application]::DoEvents(); "
                "    Start-Sleep -Milliseconds 100; "
                "  }; "
                "  if (-not $script:printed) { throw 'HTML print timeout.' }; "
                "  if (-not [string]::IsNullOrWhiteSpace($script:printErr)) { throw $script:printErr }; "
                "  Start-Sleep -Milliseconds 1000; "
                "} finally { "
                "  if (Test-Path -LiteralPath $pageSetupKey) { "
                "    if ($null -ne $oldHeader) { try { Set-ItemProperty -Path $pageSetupKey -Name header -Value $oldHeader } catch {} }; "
                "    if ($null -ne $oldFooter) { try { Set-ItemProperty -Path $pageSetupKey -Name footer -Value $oldFooter } catch {} }; "
                "  }; "
                "  if ($network -and $oldDefault -and ($oldDefault -ne $printer)) { "
                "    try { $network.SetDefaultPrinter($oldDefault) } catch {} "
                "  } "
                "}"
            )

            env = os.environ.copy()
            env["AB_PRINT_PRINTER"] = printer_name
            env["AB_PRINT_HTML"] = temp_path
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Sta",
                    "-Command",
                    ps_script,
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
                timeout=40,
                check=False,
            )
            if result.returncode != 0:
                err = (result.stderr or result.stdout or "").strip()
                raise UserError(_("Direct print failed: %s") % (err or _("PowerShell HTML print command failed.")))
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass

        return {"ok": True}

    @api.model
    def _direct_print_pos_cut(self, printer_name=""):
        if os.name != "nt":
            return {"ok": False}
        try:
            import win32print  # type: ignore
        except Exception:
            return {"ok": False}

        target_printer = str(printer_name or "").strip()
        if not target_printer:
            try:
                target_printer = str(win32print.GetDefaultPrinter() or "").strip()
            except Exception:
                target_printer = ""
        if not target_printer:
            return {"ok": False}

        printer_handle = None
        doc_started = False
        try:
            printer_handle = win32print.OpenPrinter(target_printer)
            win32print.StartDocPrinter(printer_handle, 1, ("Odoo POS Cut", None, "RAW"))
            doc_started = True
            # Cut only, no extra paper feed, to avoid blank tail output.
            win32print.WritePrinter(printer_handle, b"\x1dV\x00")
            win32print.EndDocPrinter(printer_handle)
            doc_started = False
        except Exception:
            pass
        finally:
            if doc_started and printer_handle:
                try:
                    win32print.EndDocPrinter(printer_handle)
                except Exception:
                    pass
            if printer_handle:
                try:
                    win32print.ClosePrinter(printer_handle)
                except Exception:
                    pass

        return {"ok": True}

    @api.model
    def _normalize_pos_ui_settings(self, settings):
        defaults = dict(self._POS_UI_SETTINGS_DEFAULTS)
        payload = dict(settings or {}) if isinstance(settings, dict) else {}
        out = {}
        for key, value in payload.items():
            key = str(key or "").strip()
            if not key:
                continue
            out[key] = value
        for key, default in defaults.items():
            raw = payload.get(key, default)
            out[key] = bool(raw) if isinstance(default, bool) else raw
        return out

    @api.model
    def get_pos_ui_settings(self):
        self._require_models("ab_sales_pos_settings")
        settings_model = self.env["ab_sales_pos_settings"].sudo()
        record = settings_model.search([("user_id", "=", self.env.uid)], limit=1)
        settings = self._normalize_pos_ui_settings(record.settings_json if record else {})
        return {
            "settings": settings,
            "settings_version": int(record.settings_version or 1) if record else 1,
            "last_synced_at": record.last_synced_at if record else False,
            "updated_at": record.write_date if record else False,
        }

    @api.model
    def save_pos_ui_settings(self, settings=None):
        self._require_models("ab_sales_pos_settings")
        settings_model = self.env["ab_sales_pos_settings"].sudo()
        normalized = self._normalize_pos_ui_settings(settings)
        record = settings_model.search([("user_id", "=", self.env.uid)], limit=1)
        vals = {
            "user_id": self.env.uid,
            "settings_version": 1,
            "last_synced_at": fields.Datetime.now(),
            "settings_json": normalized,
        }
        if record:
            record.write(
                {
                    "settings_json": normalized,
                    "last_synced_at": vals["last_synced_at"],
                }
            )
        else:
            record = settings_model.create(vals)
        return {
            "settings": self._normalize_pos_ui_settings(record.settings_json or normalized),
            "settings_version": int(record.settings_version or 1),
            "last_synced_at": record.last_synced_at,
            "updated_at": record.write_date,
        }

    @api.model
    def get_sales_store_settings(self):
        header_model = self.env["ab_sales_header"]
        allowed_store_ids = header_model._get_allowed_store_ids()
        default_store_id = header_model._get_default_store_id()
        stores = self.env["ab_store"].browse(allowed_store_ids).exists()
        allowed_codes = [code for code in stores.mapped("code") if code]
        default_code = ""
        if default_store_id:
            default_store = self.env["ab_store"].browse(int(default_store_id)).exists()
            default_code = (default_store.code or "").strip() if default_store else ""
        return {
            "allowed_store_codes": allowed_codes,
            "default_store_code": default_code,
        }

    @api.model
    def _inventory_balance_by_serial(self, product_serials, store_id=None):
        """
        Return dict: {product_eplus_serial: balance}

        Prefers store-specific balances when present, otherwise falls back to
        store_id IS NULL (global) balances.
        """
        if not product_serials:
            return {}

        if "ab_sales_inventory" not in self.env.registry:
            return {}

        product_serials = [int(s) for s in product_serials if s]
        if not product_serials:
            return {}

        store_id = int(store_id) if store_id else None

        if store_id:
            self.env.cr.execute(
                """
                SELECT product_eplus_serial, balance, store_id
                FROM ab_sales_inventory
                WHERE product_eplus_serial = ANY (%s)
                  AND (store_id = %s OR store_id IS NULL)
                """,
                (product_serials, store_id),
            )
        else:
            self.env.cr.execute(
                """
                SELECT product_eplus_serial, balance, store_id
                FROM ab_sales_inventory
                WHERE product_eplus_serial = ANY (%s)
                  AND store_id IS NULL
                """,
                (product_serials,),
            )

        by_serial_global = {}
        by_serial_store = {}
        for serial, balance, inv_store_id in self.env.cr.fetchall():
            serial = int(serial or 0)
            if not serial:
                continue
            bal = float(balance or 0.0)
            if inv_store_id:
                by_serial_store[serial] = max(by_serial_store.get(serial, 0.0), bal)
            else:
                by_serial_global[serial] = max(by_serial_global.get(serial, 0.0), bal)

        out = dict(by_serial_global)
        out.update(by_serial_store)
        return out

    @api.model
    def _inventory_total_and_pos_balances_by_serial(self, product_serials, store_id=None):
        """
        Return tuple:
          - total_balance_by_serial: global balance (store_id IS NULL) only
          - pos_balance_by_serial: store-specific balance only (no fallback)
        """
        if not product_serials:
            return {}, {}

        if "ab_sales_inventory" not in self.env.registry:
            return {}, {}

        product_serials = [int(s) for s in product_serials if s]
        if not product_serials:
            return {}, {}

        store_id = int(store_id) if store_id else None

        if store_id:
            self.env.cr.execute(
                """
                SELECT product_eplus_serial,
                       MAX(CASE WHEN store_id = %s THEN balance END)    AS pos_balance,
                       MAX(CASE WHEN store_id IS NULL THEN balance END) AS total_balance
                FROM ab_sales_inventory
                WHERE product_eplus_serial = ANY (%s)
                  AND balance > 0
                  AND (store_id = %s OR store_id IS NULL)
                GROUP BY product_eplus_serial
                """,
                (store_id, product_serials, store_id),
            )

            total_balance_by_serial = {}
            pos_balance_by_serial = {}
            for serial, pos_balance, total_balance in self.env.cr.fetchall():
                serial = int(serial or 0)
                if not serial:
                    continue
                pos_val = float(pos_balance or 0.0)
                total_val = float(total_balance or 0.0)
                if pos_val > 0:
                    pos_balance_by_serial[serial] = max(pos_balance_by_serial.get(serial, 0.0), pos_val)
                if total_val > 0:
                    total_balance_by_serial[serial] = max(total_balance_by_serial.get(serial, 0.0), total_val)
            return total_balance_by_serial, pos_balance_by_serial

        # No store: global only
        self.env.cr.execute(
            """
            SELECT product_eplus_serial, MAX(balance) AS balance
            FROM ab_sales_inventory
            WHERE product_eplus_serial = ANY (%s)
              AND store_id IS NULL
              AND balance > 0
            GROUP BY product_eplus_serial
            """,
            (product_serials,),
        )
        total_balance_by_serial = {int(serial): float(balance or 0.0) for serial, balance in self.env.cr.fetchall() if
                                   serial}
        return total_balance_by_serial, {}

    @api.model
    def _store_id_from_header(self, header_id):
        store_id = self.env.context.get("pos_store_id")
        if isinstance(store_id, (list, tuple)):
            store_id = store_id and store_id[0]
        try:
            store_id = int(store_id) if store_id else None
        except Exception:
            store_id = None
        if store_id:
            return store_id

        if not header_id:
            return None
        if "ab_sales_header" not in self.env.registry:
            return None
        header = self.env["ab_sales_header"].browse(int(header_id)).exists()
        return header.store_id.id if header and header.store_id else None

    @api.model
    def _require_models(self, *model_names):
        missing = [m for m in model_names if m not in self.env.registry]
        if missing:
            raise UserError(_("Missing required models: %s") % ", ".join(missing))

    @api.model
    def _safe_fields(self, model_name, desired_fields):
        self._require_models(model_name)
        model_fields = self.env[model_name]._fields
        result = [field for field in (desired_fields or []) if field in model_fields]
        if "id" not in result:
            result.insert(0, "id")
        return result

    @api.model
    def _safe_domain(self, model_name, domain):
        self._require_models(model_name)
        model_fields = self.env[model_name]._fields
        safe_domain = []
        for token in domain or []:
            if token in ("|", "&", "!"):
                safe_domain.append(token)
                continue
            if not isinstance(token, (list, tuple)) or len(token) < 3:
                continue
            field_name = token[0]
            if field_name in model_fields:
                safe_domain.append(tuple(token))
        return safe_domain

    @api.model
    def _filter_vals(self, model_name, vals):
        self._require_models(model_name)
        model_fields = self.env[model_name]._fields
        return {key: value for key, value in (vals or {}).items() if key in model_fields}

    @api.model
    def _normalize_phone(self, phone):
        digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
        if not digits:
            return ""
        if digits.startswith("0020") and len(digits) >= 14:
            digits = "0" + digits[4:]
        elif digits.startswith("20") and len(digits) >= 12:
            digits = "0" + digits[2:]
        elif len(digits) == 10 and digits.startswith("1"):
            digits = "0" + digits
        if len(digits) > 11 and digits.startswith("0"):
            digits = digits[-11:]
        if len(digits) == 11 and digits.startswith("01"):
            return digits
        return digits

    @api.model
    def _phone_variants(self, phone):
        normalized = self._normalize_phone(phone)
        raw_digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
        out = []
        for candidate in [normalized, raw_digits]:
            candidate = (candidate or "").strip()
            if not candidate or candidate in out:
                continue
            out.append(candidate)
        if normalized and len(normalized) == 11 and normalized.startswith("01"):
            suffix = normalized[1:]
            for candidate in [f"20{suffix}", f"0020{suffix}"]:
                if candidate not in out:
                    out.append(candidate)
        return out

    @api.model
    def _resolve_store_id(self, header_id=None, store_id=None):
        try:
            store_id = int(store_id) if store_id else None
        except Exception:
            store_id = None
        return store_id or self._store_id_from_header(header_id)

    @api.model
    def _customer_phone_from_header(self, header_id):
        if not header_id or "ab_sales_header" not in self.env.registry:
            return ""
        header = self.env["ab_sales_header"].browse(int(header_id)).exists()
        if not header:
            return ""
        phone = (
                header.bill_customer_phone
                or header.customer_phone
                or header.customer_mobile
                or header.new_customer_phone
                or ""
        )
        return self._normalize_phone(phone)

    @api.model
    def _rank_rows(self, rank_scope, period_days, store_id=None, customer_phone="", product_ids=None, limit=None):
        if "ab_product_rank" not in self.env.registry:
            return []
        domain = [("rank_scope", "=", rank_scope), ("period_days", "=", int(period_days or 0))]
        if store_id:
            domain.append(("store_id", "=", int(store_id)))
        if rank_scope == "customer":
            phone_variants = self._phone_variants(customer_phone)
            if not phone_variants:
                return []
            domain.append(("customer_phone", "in", phone_variants))
        else:
            domain.append(("customer_phone", "=", ""))
        if product_ids:
            domain.append(("product_id", "in", [int(pid) for pid in product_ids if pid]))
        rows = self.env["ab_product_rank"].search_read(
            domain,
            ["product_id", "order_count", "qty_total", "score"],
            limit=int(limit) if limit else None,
            order="score desc, order_count desc, qty_total desc, last_order_date desc",
        )
        out = []
        for row in rows:
            product_val = row.get("product_id")
            if isinstance(product_val, (list, tuple)):
                product_id = int(product_val[0]) if product_val and product_val[0] else 0
            else:
                product_id = int(product_val or 0)
            if not product_id:
                continue
            out.append(
                {
                    "product_id": product_id,
                    "order_count": int(row.get("order_count") or 0),
                    "qty_total": float(row.get("qty_total") or 0.0),
                    "score": float(row.get("score") or 0.0),
                }
            )
        return out

    @api.model
    def _rank_map_by_product(self, rank_rows):
        out = {}
        for row in rank_rows or []:
            product_id = int((row or {}).get("product_id") or 0)
            if not product_id:
                continue
            out[product_id] = {
                "order_count": int((row or {}).get("order_count") or 0),
                "qty_total": float((row or {}).get("qty_total") or 0.0),
                "score": float((row or {}).get("score") or 0.0),
            }
        return out

    @api.model
    def _customer_last_headers(self, customer_phone, store_id=None, limit=2):
        self._require_models("ab_sales_header")
        phone_variants = self._phone_variants(customer_phone)
        if not phone_variants:
            return self.env["ab_sales_header"]
        params = [phone_variants]
        where_store = ""
        if store_id:
            where_store = " AND store_id = %s"
            params.append(int(store_id))
        params.append(int(limit or 2))
        self.env.cr.execute(
            f"""
            SELECT id
            FROM ab_sales_header
            WHERE status IN ('pending', 'saved')
              AND regexp_replace(COALESCE(bill_customer_phone, ''), '[^0-9]', '', 'g') = ANY(%s)
              {where_store}
            ORDER BY create_date DESC, id DESC
            LIMIT %s
            """,
            tuple(params),
        )
        ids = [int(row[0]) for row in self.env.cr.fetchall() if row and row[0]]
        if not ids:
            return self.env["ab_sales_header"]
        records = self.env["ab_sales_header"].browse(ids).exists()
        order_map = {rid: idx for idx, rid in enumerate(ids)}
        return records.sorted(key=lambda r: order_map.get(r.id, 999999))

    @api.model
    def _recent_customer_product_ids(self, customer_phone, store_id=None, invoice_limit=2, max_products=12):
        self._require_models("ab_sales_line")
        headers = self._customer_last_headers(customer_phone, store_id=store_id, limit=invoice_limit)
        if not headers:
            return []
        header_ids = headers.ids
        lines = self.env["ab_sales_line"].search(
            [("header_id", "in", header_ids), ("product_id", "!=", False), ("qty", ">", 0)],
            order="id desc",
        )
        by_header = {}
        for line in lines:
            hid = line.header_id.id
            by_header.setdefault(hid, []).append(line)
        out = []
        seen = set()
        for hid in header_ids:
            for line in by_header.get(hid, []):
                pid = line.product_id.id
                if not pid or pid in seen:
                    continue
                out.append(pid)
                seen.add(pid)
                if len(out) >= int(max_products or 12):
                    return out
        return out

    @api.model
    def _frequent_customer_product_ids_live(self, customer_phone, store_id=None, period_days=90, max_products=12):
        self._require_models("ab_sales_header", "ab_sales_line")
        phone_variants = self._phone_variants(customer_phone)
        if not phone_variants:
            return []

        max_products = max(1, int(max_products or 12))
        period_days = max(1, int(period_days or 90))
        since_date = fields.Datetime.now() - timedelta(days=period_days)

        params = [since_date, phone_variants]
        where_store = ""
        if store_id:
            where_store = " AND h.store_id = %s"
            params.append(int(store_id))
        params.append(max_products)

        self.env.cr.execute(
            f"""
            SELECT
                l.product_id,
                COUNT(DISTINCT h.id) AS order_count,
                SUM(COALESCE(l.qty, 0.0)) AS qty_total,
                MAX(h.create_date) AS last_order_date
            FROM ab_sales_line l
            JOIN ab_sales_header h ON h.id = l.header_id
            WHERE h.status IN ('pending', 'saved')
              AND h.create_date >= %s
              AND l.product_id IS NOT NULL
              AND COALESCE(l.qty, 0.0) > 0
              AND regexp_replace(COALESCE(h.bill_customer_phone, ''), '[^0-9]', '', 'g') = ANY(%s)
              {where_store}
            GROUP BY l.product_id
            ORDER BY order_count DESC, qty_total DESC, last_order_date DESC, l.product_id DESC
            LIMIT %s
            """,
            tuple(params),
        )
        return [int(row[0]) for row in self.env.cr.fetchall() if row and row[0]]

    @api.model
    def _blend_customer_product_ids(self, frequent_ids, recent_ids, limit):
        frequent_ids = [int(pid) for pid in (frequent_ids or []) if pid][:12]
        recent_ids = [int(pid) for pid in (recent_ids or []) if pid][:12]
        limit = max(1, int(limit or 24))
        target_frequent = min(len(frequent_ids), int(round(limit * 0.6)))
        target_recent = min(len(recent_ids), max(0, limit - target_frequent))

        ordered = []
        source = {}

        def _push(ids, max_count, tag):
            added = 0
            for pid in ids:
                if pid in ordered:
                    source[pid] = "frequent_recent"
                    continue
                ordered.append(pid)
                source[pid] = tag
                added += 1
                if len(ordered) >= limit or added >= max_count:
                    break

        _push(frequent_ids, target_frequent, "frequent")
        _push(recent_ids, target_recent, "recent")
        _push(frequent_ids, limit, "frequent")
        _push(recent_ids, limit, "recent")
        return ordered[:limit], source

    @api.model
    def _customer_activity_tag(self, last_purchase_date):
        if not last_purchase_date:
            return ""
        now = fields.Datetime.now()
        delta = now - last_purchase_date
        days = delta.days if hasattr(delta, "days") else 0
        if days <= 45:
            return "عميل دائم"
        if days >= 120:
            return "غير نشط"
        return ""

    @api.model
    def search_products(
            self,
            query="",
            limit=60,
            has_balance=True,
            has_pos_balance=False,
            header_id=None,
            store_id=None,
            customer_phone=None,
    ):
        self._require_models("ab_product", "ab_product_uom")
        Product = self.env["ab_product"]
        base_domain = [("active", "=", True)]
        raw_query = (query or "").strip()
        query_code = ""
        query_like = ""
        if raw_query:
            query_code = raw_query
            query_like = raw_query.replace("*", "%").replace(" ", "%") + "%"
        fields_list = self._safe_fields(
            "ab_product",
            [
                "name",
                "product_card_name",
                "code",
                "is_service",
                "default_price",
                "allow_sell_fraction",
                "eplus_serial",
                "uom_id",
                "uom_category_id",
            ],
        )
        limit = max(1, min(120, int(limit or 60)))
        want_balance_only = bool(has_balance)
        want_pos_balance_only = bool(has_pos_balance)
        chunk_size = max(200, limit * 4)

        store_id = self._resolve_store_id(header_id=header_id, store_id=store_id)
        customer_phone = self._normalize_phone(customer_phone) or self._customer_phone_from_header(header_id)

        def _uom_id_from_val(val):
            if isinstance(val, (list, tuple)):
                return int(val[0]) if val and val[0] else 0
            try:
                return int(val or 0)
            except Exception:
                return 0

        def _attach_uom_factors(rows):
            rows = rows or []
            uom_ids = []
            for r in rows:
                uom_ids.append(_uom_id_from_val(r.get("uom_id")))
            uom_ids = [uid for uid in set(uom_ids) if uid]
            if not uom_ids:
                return rows
            uoms = self.env["ab_product_uom"].browse(uom_ids).read(["factor"])
            factor_by_id = {int(u["id"]): float(u.get("factor") or 1.0) for u in uoms}
            for r in rows:
                uom_id = _uom_id_from_val(r.get("uom_id"))
                factor = factor_by_id.get(uom_id, 1.0)
                r["uom_factor"] = factor
                r["default_uom_factor"] = factor
            return rows

        def _run_search(search_domain, sql_filter=None):
            search_domain = self._safe_domain("ab_product", search_domain)

            if want_pos_balance_only and store_id and not raw_query:
                params = [store_id]
                extra_where = ""
                if sql_filter:
                    extra_where = f" AND {sql_filter['where']}"
                    params.extend(sql_filter["params"])
                if want_balance_only:
                    extra_where += " AND g.balance > 0"
                params.append(limit)

                self.env.cr.execute(
                    f"""
                    SELECT
                        p.id,
                        MAX(i.balance) AS pos_balance,
                        COALESCE(MAX(g.balance), 0) AS total_balance
                    FROM ab_product p
                    JOIN ab_sales_inventory i
                      ON i.product_eplus_serial = p.eplus_serial
                     AND i.store_id = %s
                     AND i.balance > 0
                    LEFT JOIN ab_sales_inventory g
                      ON g.product_eplus_serial = p.eplus_serial
                     AND g.store_id IS NULL
                     AND g.balance > 0
                    WHERE p.active = TRUE
                      {extra_where}
                    GROUP BY p.id, p.name
                    ORDER BY p.name
                    LIMIT %s
                    """,
                    tuple(params),
                )
                rows = self.env.cr.fetchall()
                if not rows:
                    return []

                pos_balance_by_product_id = {
                    int(pid): float(pos_bal or 0.0) for pid, pos_bal, _total_bal in rows if pid
                }
                total_balance_by_product_id = {
                    int(pid): float(total_bal or 0.0) for pid, _pos_bal, total_bal in rows if pid
                }
                product_ids = [int(pid) for pid, _pos_bal, _total_bal in rows if pid]
                products = Product.browse(product_ids).read(fields_list)
                _attach_uom_factors(products)
                by_id = {p["id"]: p for p in products}
                out = []
                for pid in product_ids:
                    row = by_id.get(pid)
                    if not row:
                        continue
                    pos_balance = float(pos_balance_by_product_id.get(pid, 0.0) or 0.0)
                    total_balance = float(total_balance_by_product_id.get(pid, 0.0) or 0.0)
                    row["pos_balance"] = pos_balance
                    row["has_pos_balance"] = bool(pos_balance > 0)
                    row["balance"] = total_balance
                    row["has_balance"] = bool(total_balance > 0)
                    out.append(row)
                return out[:limit]

            offset = 0
            out = []
            seen_ids = set()
            while len(out) < limit:
                rows = Product.search_read(search_domain, fields_list, limit=chunk_size, offset=offset, order="name")
                if not rows:
                    break

                _attach_uom_factors(rows)
                serials = []
                for row in rows:
                    try:
                        serials.append(int(row.get("eplus_serial") or 0))
                    except Exception:
                        serials.append(0)

                total_balance_by_serial, pos_balance_by_serial = self._inventory_total_and_pos_balances_by_serial(
                    serials, store_id=store_id
                )

                for row in rows:
                    rid = row.get("id")
                    if not rid or rid in seen_ids:
                        continue

                    serial = 0
                    try:
                        serial = int(row.get("eplus_serial") or 0)
                    except Exception:
                        serial = 0

                    total_balance = float(total_balance_by_serial.get(serial, 0.0) or 0.0) if serial else 0.0
                    pos_balance = float(pos_balance_by_serial.get(serial, 0.0) or 0.0) if serial else 0.0
                    row["balance"] = total_balance
                    row["has_balance"] = bool(total_balance > 0)
                    row["pos_balance"] = pos_balance
                    row["has_pos_balance"] = bool(pos_balance > 0)
                    is_service_match = bool(raw_query and row.get("is_service"))

                    if want_balance_only and not row["has_balance"] and not is_service_match:
                        continue
                    if want_pos_balance_only and not row["has_pos_balance"] and not is_service_match:
                        continue

                    seen_ids.add(rid)
                    out.append(row)
                    if len(out) >= limit:
                        break

                offset += chunk_size

            return out[:limit]

        def _annotate(rows, pinned_ids=None, source_map=None):
            rows = rows or []
            pinned_set = set(int(pid) for pid in (pinned_ids or []) if pid)
            source_map = source_map or {}
            product_ids = [int(r.get("id") or 0) for r in rows if r.get("id")]
            customer_rank_rows = self._rank_rows(
                "customer", 90, store_id=None, customer_phone=customer_phone, product_ids=product_ids
            )
            customer_map = self._rank_map_by_product(customer_rank_rows)
            for row in rows:
                pid = int(row.get("id") or 0)
                cust = customer_map.get(pid, {})
                row["customer_order_count_3m"] = int(cust.get("order_count") or 0)
                row["is_top_customer"] = bool(cust.get("order_count"))
                row["branch_order_count_30d"] = 0
                row["is_top_branch"] = False
                row["is_pinned"] = pid in pinned_set
                row["rank_source"] = source_map.get(pid, "")
            return rows

        if raw_query:
            code_domain = [("code", "=ilike", query_code)] + base_domain
            code_results = _run_search(code_domain, sql_filter={"where": "p.code ILIKE %s", "params": [query_code]})
            rows = code_results
            if not rows:
                name_domain = [("name", "=ilike", query_like)] + base_domain
                rows = _run_search(name_domain, sql_filter={"where": "p.name ILIKE %s", "params": [query_like]})
            if not rows:
                return []

            pinned_ids = []
            if customer_phone:
                rank_rows = self._rank_rows(
                    "customer",
                    90,
                    store_id=None,
                    customer_phone=customer_phone,
                    product_ids=[row["id"] for row in rows if row.get("id")],
                )
                pinned_ids = [row["product_id"] for row in rank_rows][:5]
            if pinned_ids:
                by_id = {int(row.get("id")): row for row in rows if row.get("id")}
                ordered = [by_id[pid] for pid in pinned_ids if pid in by_id]
                ordered += [row for row in rows if int(row.get("id") or 0) not in pinned_ids]
                rows = ordered[:limit]

            return _annotate(rows, pinned_ids=pinned_ids)[:limit]

        if customer_phone:
            frequent_rows = self._rank_rows(
                "customer", 90, store_id=None, customer_phone=customer_phone, limit=12
            )
            frequent_ids = [int(row["product_id"]) for row in frequent_rows if row.get("product_id")]
            if len(frequent_ids) < 12:
                live_ids = self._frequent_customer_product_ids_live(
                    customer_phone=customer_phone,
                    store_id=None,
                    period_days=90,
                    max_products=12,
                )
                seen = set(frequent_ids)
                for pid in live_ids:
                    if pid in seen:
                        continue
                    frequent_ids.append(pid)
                    seen.add(pid)
                    if len(frequent_ids) >= 12:
                        break
            recent_ids = self._recent_customer_product_ids(
                customer_phone, store_id=None, invoice_limit=2, max_products=12
            )
            blended_ids, source_map = self._blend_customer_product_ids(frequent_ids, recent_ids, limit)
            if blended_ids:
                blended_rows = _run_search(
                    [("id", "in", blended_ids)] + base_domain,
                    sql_filter={"where": "p.id = ANY(%s)", "params": [blended_ids]},
                )
                by_id = {int(row["id"]): row for row in blended_rows if row.get("id")}
                ordered = [by_id[pid] for pid in blended_ids if pid in by_id]
                return _annotate(ordered, source_map=source_map)[:limit]

        return []

    @api.model
    def pos_customer_insights(self, header_id=None, store_id=None, customer_phone=None, customer_name=None):
        self._require_models("ab_sales_header", "ab_sales_line")
        store_id = self._resolve_store_id(header_id=header_id, store_id=store_id)
        customer_phone = self._normalize_phone(customer_phone) or self._customer_phone_from_header(header_id)
        customer_name = (customer_name or "").strip()
        if not customer_phone:
            return {"customer": {"phone": "", "name": customer_name}, "last_invoice": False}

        last_headers = self._customer_last_headers(customer_phone, store_id=store_id, limit=1)
        last_header = last_headers[:1]
        if not last_header:
            return {
                "customer": {
                    "phone": customer_phone,
                    "name": customer_name,
                    "last_address": "",
                    "last_purchase_date": False,
                    "activity_tag": "",
                },
                "last_invoice": False,
            }

        header = last_header[0]
        lines = self.env["ab_sales_line"].search(
            [("header_id", "=", header.id), ("product_id", "!=", False), ("qty", ">", 0)],
            order="id asc",
        )
        invoice_lines = []
        for line in lines:
            invoice_lines.append(
                {
                    "line_id": line.id,
                    "product_id": line.product_id.id,
                    "product_name": line.product_id.display_name or line.product_id.name or "",
                    "product_code": line.product_code or line.product_id.code or "",
                    "qty": float(line.qty or 0.0),
                    "sell_price": float(line.sell_price or 0.0),
                    "net_amount": float(line.net_amount or 0.0),
                }
            )

        last_address = (
                (header.bill_customer_address or "").strip()
                or (header.invoice_address or "").strip()
                or (header.customer_address or "").strip()
        )
        display_name = (
                (header.bill_customer_name or "").strip()
                or (header.customer_id.display_name if header.customer_id else "")
                or customer_name
        )

        return {
            "customer": {
                "phone": customer_phone,
                "name": display_name,
                "last_address": last_address,
                "last_purchase_date": header.create_date,
                "activity_tag": self._customer_activity_tag(header.create_date),
            },
            "last_invoice": {
                "id": header.id,
                "store_id": header.store_id.id if header.store_id else False,
                "date": header.create_date,
                "total": float(header.total_price or 0.0),
                "net_total": float(header.total_net_amount or 0.0),
                "line_count": len(invoice_lines),
                "lines": invoice_lines,
            },
        }

    @api.model
    def pos_customer_invoices(self, header_id=None, store_id=None, customer_phone=None, limit=20):
        self._require_models("ab_sales_header", "ab_sales_line")
        customer_phone = self._normalize_phone(customer_phone) or self._customer_phone_from_header(header_id)
        if not customer_phone:
            return []

        limit = max(1, min(50, int(limit or 20)))
        headers = self._customer_last_headers(customer_phone, store_id=None, limit=limit)
        if not headers:
            return []

        header_ids = headers.ids
        lines = self.env["ab_sales_line"].search(
            [("header_id", "in", header_ids), ("product_id", "!=", False), ("qty", ">", 0)],
            order="header_id desc, id asc",
        )
        lines_by_header = {}
        for line in lines:
            hid = line.header_id.id
            lines_by_header.setdefault(hid, []).append(
                {
                    "line_id": line.id,
                    "product_id": line.product_id.id,
                    "product_name": line.product_id.display_name or line.product_id.name or "",
                    "product_code": line.product_code or line.product_id.code or "",
                    "qty": float(line.qty or 0.0),
                    "sell_price": float(line.sell_price or 0.0),
                    "net_amount": float(line.net_amount or 0.0),
                }
            )

        out = []
        for header in headers:
            invoice_lines = lines_by_header.get(header.id, [])
            out.append(
                {
                    "id": header.id,
                    "eplus_serial": int(header.eplus_serial or 0),
                    "date": header.create_date,
                    "store_id": header.store_id.id if header.store_id else False,
                    "store_name": header.store_id.name if header.store_id else "",
                    "store_code": header.store_id.code if header.store_id else "",
                    "total": float(header.total_price or 0.0),
                    "net_total": float(header.total_net_amount or 0.0),
                    "line_count": len(invoice_lines),
                    "lines": invoice_lines,
                }
            )
        return out

    @api.model
    def apply_products(self, header_id, items):
        self._require_models("ab_sales_header", "ab_sales_line", "ab_product")
        if not header_id:
            raise UserError(_("Missing header_id."))

        header = self.env["ab_sales_header"].browse(int(header_id)).exists()
        if not header:
            raise UserError(_("Sales header not found."))

        items = items or []
        if not isinstance(items, list):
            raise UserError(_("Invalid items payload."))

        SalesLine = self.env["ab_sales_line"]
        lines_to_recompute = SalesLine.browse()
        created = 0
        updated = 0

        existing_lines_by_product = {l.product_id.id: l for l in header.line_ids}
        product_ids = []
        for item in items:
            try:
                pid = int((item or {}).get("product_id") or 0)
            except Exception:
                pid = 0
            if pid:
                product_ids.append(pid)
        products = self.env["ab_product"].browse(list(set(product_ids))).exists()
        default_price_by_product = {p.id: (p.default_price or 0.0) for p in products}
        default_uom_by_product = {p.id: (p.uom_id.id if p.uom_id else False) for p in products}

        for item in items:
            item = item or {}
            product_id = item.get("product_id")
            qty = item.get("qty")
            try:
                product_id = int(product_id)
                qty = float(qty)
            except Exception:
                continue
            if not product_id or qty <= 0:
                continue

            if product_id in existing_lines_by_product:
                line = existing_lines_by_product[product_id]
                current_qty = float(getattr(line, "qty", 0.0) or 0.0)
                new_qty = current_qty + qty
                write_vals = {"qty_str": str(new_qty)}
                if header.status not in ("saved", "pending"):
                    write_vals["sell_price"] = default_price_by_product.get(product_id, 0.0)
                write_vals = self._filter_vals("ab_sales_line", write_vals)
                if write_vals:
                    line.write(write_vals)
                    updated += 1
                    lines_to_recompute |= line
                continue

            create_vals = {
                "header_id": header.id,
                "product_id": product_id,
                "qty_str": str(qty),
            }
            if header.status not in ("saved", "pending"):
                create_vals["sell_price"] = default_price_by_product.get(product_id, 0.0)
            if default_uom_by_product.get(product_id):
                create_vals["uom_id"] = default_uom_by_product.get(product_id)
            create_vals = self._filter_vals("ab_sales_line", create_vals)
            new_line = SalesLine.create(create_vals)
            created += 1
            lines_to_recompute |= new_line

        # Recompute inventory JSON after applying products (if supported by the model).
        if lines_to_recompute and hasattr(lines_to_recompute, "_recompute_inventory_json"):
            lines_to_recompute._recompute_inventory_json()

        return {"created": created, "updated": updated}
