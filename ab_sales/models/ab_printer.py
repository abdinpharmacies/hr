# -*- coding: utf-8 -*-

import os
import socket
import subprocess
import tempfile
from pathlib import Path

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import find_in_path


class AbPrinter(models.Model):
    _name = "ab_printer"
    _description = "Printer Configuration"
    _order = "is_default desc, name asc, id asc"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    is_default = fields.Boolean(string="Default", default=False)
    ip = fields.Char(string="IP / Host")
    port = fields.Integer(default=9100)
    username = fields.Char()
    password = fields.Char()
    printer_name = fields.Char(required=True, string="Printer / Share Name")
    protocol = fields.Selection(
        selection=[
            ("shared", "Shared"),
            ("connected", "Connected"),
            ("network", "Network"),
        ],
        required=True,
        default="connected",
    )
    paper_size = fields.Selection(
        selection=[
            ("pos_80mm", "POS 80mm"),
            ("a4", "A4"),
        ],
        required=True,
        default="a4",
    )
    notes = fields.Text()

    _uniq_name = models.Constraint(
        "UNIQUE(name)",
        "Printer name must be unique.",
    )

    @api.model
    def _safe_find_binary(self, binary_name):
        try:
            return find_in_path(binary_name)
        except IOError:
            raise UserError(_("Required print binary is missing: %s") % binary_name)

    @api.constrains("protocol", "ip", "printer_name", "port")
    def _check_protocol_requirements(self):
        for rec in self:
            protocol = (rec.protocol or "").strip()
            host = (rec.ip or "").strip()
            queue = (rec.printer_name or "").strip()
            if protocol == "shared":
                if not host:
                    raise ValidationError(_("Shared printers require IP / Host."))
                if not queue:
                    raise ValidationError(_("Shared printers require Printer / Share Name."))
            elif protocol == "connected":
                if not queue:
                    raise ValidationError(_("Connected printers require Printer / Share Name."))
            elif protocol == "network":
                if not host:
                    raise ValidationError(_("Network printers require IP / Host."))
            if rec.port and (rec.port < 1 or rec.port > 65535):
                raise ValidationError(_("Port must be between 1 and 65535."))

    @api.constrains("is_default")
    def _check_single_default(self):
        defaults = self.search([("is_default", "=", True)])
        if len(defaults) > 1:
            raise ValidationError(_("Only one default printer is allowed."))

    @api.model_create_multi
    def create(self, vals_list):
        if any(vals.get("is_default") for vals in vals_list):
            self.search([("is_default", "=", True)]).write({"is_default": False})
        records = super().create(vals_list)
        records._clear_other_defaults()
        return records

    def write(self, vals):
        if vals.get("is_default"):
            self.search([("id", "not in", self.ids), ("is_default", "=", True)]).write({"is_default": False})
        res = super().write(vals)
        if "is_default" in vals and vals.get("is_default"):
            self._clear_other_defaults()
        return res

    def _clear_other_defaults(self):
        for rec in self.filtered("is_default"):
            other_defaults = self.search([("id", "!=", rec.id), ("is_default", "=", True)])
            if other_defaults:
                other_defaults.write({"is_default": False})

    def _sanitize_error(self, error_text):
        text = str(error_text or "").strip()
        if self.password:
            text = text.replace(self.password, "***")
        return text

    def _selection_label(self, field_name, value):
        field = self._fields.get(field_name)
        mapping = dict(field.selection) if field and field.selection else {}
        return mapping.get(value, value)

    def build_display_label(self):
        self.ensure_one()
        protocol_label = self._selection_label("protocol", self.protocol)
        paper_label = self._selection_label("paper_size", self.paper_size)
        return f"{self.name} | {protocol_label} | {paper_label}"

    def to_print_payload(self):
        payload = []
        for rec in self:
            payload.append(
                {
                    "id": rec.id,
                    "name": rec.name,
                    "label": rec.build_display_label(),
                    "protocol": rec.protocol,
                    "paper_size": rec.paper_size,
                    "ip": (rec.ip or "").strip(),
                    "port": int(rec.port or 9100),
                    "username": (rec.username or "").strip(),
                    "printer_name": (rec.printer_name or "").strip(),
                    "is_default": bool(rec.is_default),
                }
            )
        return payload

    @api.model
    def get_active_printers(self, paper_size=None):
        domain = [("active", "=", True)]
        size = str(paper_size or "").strip()
        if size in ("pos_80mm", "a4"):
            domain.append(("paper_size", "=", size))
        return self.search(domain, order=self._order)

    @api.model
    def get_default_printer(self, paper_size=None):
        domain = [("active", "=", True), ("is_default", "=", True)]
        size = str(paper_size or "").strip()
        if size in ("pos_80mm", "a4"):
            domain.append(("paper_size", "=", size))
        printer = self.search(domain, limit=1)
        if printer:
            return printer
        fallback_domain = [("active", "=", True)]
        if size in ("pos_80mm", "a4"):
            fallback_domain.append(("paper_size", "=", size))
        return self.search(fallback_domain, limit=1)

    def validate_for_print(self):
        self.ensure_one()
        # Reuse ORM constraints to ensure protocol-specific requirements are enforced.
        self._check_protocol_requirements()
        return True

    def _detect_os_name(self, os_name=None):
        normalized = str(os_name or "").strip().lower()
        if normalized in ("linux", "windows"):
            return normalized
        return "windows" if os.name == "nt" else "linux"

    def _build_print_command(self, file_path, os_name=None):
        self.ensure_one()
        self.validate_for_print()
        target_os = self._detect_os_name(os_name=os_name)
        protocol = (self.protocol or "").strip()
        host = (self.ip or "").strip()
        queue = (self.printer_name or "").strip()

        if target_os == "linux":
            if protocol == "shared":
                self._safe_find_binary("smbclient")
                smb_target = f"//{host}/{queue}"
                if self.username:
                    return {
                        "kind": "subprocess",
                        "args": [
                            "smbclient",
                            smb_target,
                            "-U",
                            f"{self.username}%{self.password or ''}",
                            "-c",
                            f'print "{file_path}"',
                        ],
                    }
                return {
                    "kind": "subprocess",
                    "args": [
                        "smbclient",
                        smb_target,
                        "-N",
                        "-c",
                        f'print "{file_path}"',
                    ],
                }
            if protocol == "connected":
                self._safe_find_binary("lp")
                return {
                    "kind": "subprocess",
                    "args": ["lp", "-d", queue, str(file_path)],
                }
            if protocol == "network":
                return {
                    "kind": "raw_tcp",
                    "host": host,
                    "port": int(self.port or 9100),
                }
        else:
            if protocol == "shared":
                return {
                    "kind": "windows_shared",
                    "host": host,
                    "share": queue,
                    "username": (self.username or "").strip(),
                    "password": self.password or "",
                }
            if protocol == "connected":
                return {
                    "kind": "windows_connected",
                    "printer_name": queue,
                }
            if protocol == "network":
                return {
                    "kind": "raw_tcp",
                    "host": host,
                    "port": int(self.port or 9100),
                }

        raise UserError(_("Unsupported print combination: %s / %s") % (target_os, protocol))

    def _run_subprocess(self, args, timeout=45):
        self.ensure_one()
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            check=False,
        )
        if result.returncode != 0:
            err = self._sanitize_error((result.stderr or result.stdout or "").strip())
            raise UserError(_("Print command failed: %s") % (err or _("Command execution failed.")))

    def _send_raw_tcp(self, file_path, host, port=9100):
        self.ensure_one()
        with open(file_path, "rb") as stream:
            data = stream.read()
        try:
            with socket.create_connection((host, int(port or 9100)), timeout=10) as conn:
                conn.sendall(data)
        except Exception as exc:
            raise UserError(_("Raw TCP print failed: %s") % self._sanitize_error(str(exc)))

    def _dispatch_windows_shared(self, file_path, host, share, username="", password=""):
        self.ensure_one()
        target = r"\\%s\%s" % (host, share)
        connected = False
        if username:
            self._run_subprocess(
                ["net", "use", target, password or "", f"/user:{username}"],
                timeout=30,
            )
            connected = True
        try:
            self._run_subprocess(
                ["cmd", "/c", f'copy /b "{file_path}" "{target}"'],
                timeout=30,
            )
        finally:
            if connected:
                subprocess.run(
                    ["net", "use", target, "/delete", "/y"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=20,
                    check=False,
                )

    def _dispatch_windows_connected(self, file_path, printer_name):
        self.ensure_one()
        try:
            import win32print  # type: ignore
        except Exception as exc:
            raise UserError(
                _("Windows installed-printer RAW printing requires pywin32: %s") % self._sanitize_error(str(exc))
            )

        handle = None
        doc_started = False
        page_started = False
        try:
            handle = win32print.OpenPrinter(printer_name)
            win32print.StartDocPrinter(handle, 1, ("Odoo RAW Print", None, "RAW"))
            doc_started = True
            win32print.StartPagePrinter(handle)
            page_started = True
            with open(file_path, "rb") as stream:
                win32print.WritePrinter(handle, stream.read())
            win32print.EndPagePrinter(handle)
            page_started = False
            win32print.EndDocPrinter(handle)
            doc_started = False
        except Exception as exc:
            raise UserError(_("Windows RAW spooler print failed: %s") % self._sanitize_error(str(exc)))
        finally:
            if page_started and handle:
                try:
                    win32print.EndPagePrinter(handle)
                except Exception:
                    pass
            if doc_started and handle:
                try:
                    win32print.EndDocPrinter(handle)
                except Exception:
                    pass
            if handle:
                try:
                    win32print.ClosePrinter(handle)
                except Exception:
                    pass

    def _dispatch_print_file(self, file_path, os_name=None):
        self.ensure_one()
        command = self._build_print_command(file_path, os_name=os_name)
        kind = command.get("kind")
        if kind == "subprocess":
            self._run_subprocess(command.get("args") or [])
            return
        if kind == "raw_tcp":
            self._send_raw_tcp(
                file_path=file_path,
                host=command.get("host") or "",
                port=command.get("port") or 9100,
            )
            return
        if kind == "windows_shared":
            self._dispatch_windows_shared(
                file_path=file_path,
                host=command.get("host") or "",
                share=command.get("share") or "",
                username=command.get("username") or "",
                password=command.get("password") or "",
            )
            return
        if kind == "windows_connected":
            self._dispatch_windows_connected(
                file_path=file_path,
                printer_name=command.get("printer_name") or "",
            )
            return
        raise UserError(_("Unsupported print command type: %s") % str(kind or "unknown"))

    def _render_html_to_pdf(self, html_content, workdir):
        self.ensure_one()
        wkhtmltopdf_bin = self._safe_find_binary("wkhtmltopdf")
        html_file = workdir / "print-job.html"
        pdf_file = workdir / "print-job.pdf"
        html_file.write_text(str(html_content or ""), encoding="utf-8")
        result = subprocess.run(
            [
                wkhtmltopdf_bin,
                "--encoding",
                "utf-8",
                "--quiet",
                str(html_file),
                str(pdf_file),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
            check=False,
        )
        if result.returncode != 0:
            err = self._sanitize_error((result.stderr or result.stdout or "").strip())
            raise UserError(_("PDF rendering failed: %s") % (err or _("wkhtmltopdf command failed.")))
        return pdf_file

    def _render_html_to_escpos_bin(self, html_content, workdir):
        self.ensure_one()
        wkhtmltoimage_bin = self._safe_find_binary("wkhtmltoimage")
        try:
            from escpos.printer import File as EscposFile  # type: ignore
        except Exception as exc:
            raise UserError(
                _("Python package 'python-escpos' is required for POS binary printing: %s")
                % self._sanitize_error(str(exc))
            )
        try:
            from PIL import Image, ImageChops, ImageOps  # type: ignore
        except Exception as exc:
            raise UserError(
                _("Python package 'Pillow' is required for POS image processing: %s")
                % self._sanitize_error(str(exc))
            )

        html_file = workdir / "receipt.html"
        raw_png = workdir / "receipt-raw.png"
        final_png = workdir / "receipt-final.png"
        escpos_bin = workdir / "receipt-print.bin"
        html_file.write_text(str(html_content or ""), encoding="utf-8")

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
            err = self._sanitize_error((image_result.stderr or image_result.stdout or "").strip())
            raise UserError(_("POS image rendering failed: %s") % (err or _("wkhtmltoimage command failed.")))

        if not raw_png.exists():
            raise UserError(_("POS image rendering failed: output image not generated."))

        try:
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
                    border=(0, 0, 0, 24),
                    fill="white",
                )
                image = image.convert("L")
                image = image.point(lambda px: 0 if px < 188 else 255, mode="1")
                image.save(final_png, format="PNG")
        except Exception as exc:
            raise UserError(_("POS image processing failed: %s") % self._sanitize_error(str(exc)))

        try:
            printer = EscposFile(str(escpos_bin))
            printer.image(str(final_png))
            printer.cut()
            printer.close()
        except Exception as exc:
            raise UserError(_("ESC/POS binary build failed: %s") % self._sanitize_error(str(exc)))

        return escpos_bin

    def dispatch_print_html(self, html_content, print_format=None, os_name=None):
        self.ensure_one()
        content = str(html_content or "").strip()
        if not content:
            raise UserError(_("Nothing to print."))
        self.validate_for_print()
        fmt = "pos_80mm" if str(print_format or "").strip() == "pos_80mm" else "a4"
        if self.paper_size in ("pos_80mm", "a4") and fmt != self.paper_size:
            fmt = self.paper_size

        with tempfile.TemporaryDirectory(prefix="odoo_ab_printer_") as tmpdir:
            workdir = Path(tmpdir)
            if fmt == "pos_80mm":
                file_path = self._render_html_to_escpos_bin(content, workdir)
            else:
                file_path = self._render_html_to_pdf(content, workdir)
            self._dispatch_print_file(str(file_path), os_name=os_name)

        return {
            "ok": True,
            "printer_id": self.id,
            "printer_name": self.build_display_label(),
            "print_format": fmt,
        }

    def action_test_print(self):
        self.ensure_one()
        now_text = fields.Datetime.context_timestamp(self, fields.Datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
        html_content = (
            "<html><head><meta charset='utf-8'/></head><body>"
            f"<h3>Test Print - {self.name}</h3>"
            f"<p>Time: {now_text}</p>"
            f"<p>Protocol: {self._selection_label('protocol', self.protocol)}</p>"
            f"<p>Paper: {self._selection_label('paper_size', self.paper_size)}</p>"
            f"<p>Branch: العروبة 1 سوهاج</p>"
            f"<p>العميل: عميل 1 وهمي</p>"
            f"<p>-------------------------</p>"
            f"<p>Cataflam 50 mg 9 sachets</p>"
            f"<p>Abimol 500 TAB</p>"
            f"<p>Bristaflam 50 tab</p>"
            f"<p>__________________________</p>"
            "</body></html>"
        )
        self.dispatch_print_html(html_content, print_format=self.paper_size)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Printer Test"),
                "message": _("Test print sent to %s.") % self.build_display_label(),
                "type": "success",
                "sticky": False,
            },
        }
