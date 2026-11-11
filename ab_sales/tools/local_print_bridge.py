#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse


def _json_bytes(payload):
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def _run_process(cmd, *, input_text=None, env=None, timeout=30):
    return subprocess.run(
        cmd,
        input=input_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=timeout,
        check=False,
    )


def list_printers():
    names = []
    default_name = ""
    if os.name == "nt":
        try:
            result = _run_process(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Get-Printer | Select-Object -ExpandProperty Name",
                ],
                timeout=8,
            )
            if result.returncode == 0:
                for line in (result.stdout or "").splitlines():
                    name = (line or "").strip()
                    if name:
                        names.append(name)
        except Exception:
            pass
        try:
            result = _run_process(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "(Get-CimInstance Win32_Printer -Filter \"Default=True\" | Select-Object -First 1 -ExpandProperty Name)",
                ],
                timeout=8,
            )
            if result.returncode == 0:
                default_name = str(result.stdout or "").strip()
        except Exception:
            pass
    else:
        try:
            if shutil.which("lpstat"):
                result = _run_process(["lpstat", "-a"], timeout=8)
                if result.returncode == 0:
                    for line in (result.stdout or "").splitlines():
                        text = (line or "").strip()
                        if text:
                            names.append(text.split()[0])
            if shutil.which("lpstat"):
                result = _run_process(["lpstat", "-d"], timeout=8)
                if result.returncode == 0:
                    txt = (result.stdout or "").strip()
                    marker = "system default destination:"
                    if txt.lower().startswith(marker):
                        default_name = txt[len(marker):].strip()
        except Exception:
            pass

    seen = set()
    unique = []
    for name in names:
        text = str(name or "").strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(text)
    unique.sort(key=lambda n: n.casefold())
    return unique, str(default_name or "").strip()


def print_text(content, printer_name):
    text = str(content or "").strip()
    if not text:
        raise RuntimeError("Nothing to print.")

    printer = str(printer_name or "").strip()
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
        env["AB_PRINT_PRINTER"] = printer
        result = _run_process(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                ps_script,
            ],
            input_text=text + "\n",
            env=env,
            timeout=35,
        )
        if result.returncode != 0:
            err = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(err or "PowerShell print command failed.")
        return

    if not shutil.which("lp"):
        raise RuntimeError("Direct print is not available on this machine (missing 'lp').")
    cmd = ["lp"]
    if printer:
        cmd.extend(["-d", printer])
    result = _run_process(cmd, input_text=text + "\n", timeout=35)
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(err or "lp print command failed.")


def print_html(content, printer_name):
    html = str(content or "").strip()
    if not html:
        raise RuntimeError("Nothing to print.")
    printer = str(printer_name or "").strip()

    if os.name != "nt":
        print_text(html, printer)
        return

    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as tmp:
            tmp.write(html)
            temp_path = tmp.name

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
            "  Start-Sleep -Milliseconds 800; "
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
        env["AB_PRINT_PRINTER"] = printer
        env["AB_PRINT_HTML"] = temp_path
        result = _run_process(
            [
                "powershell",
                "-NoProfile",
                "-Sta",
                "-Command",
                ps_script,
            ],
            env=env,
            timeout=45,
        )
        if result.returncode != 0:
            err = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(err or "HTML direct print failed.")
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception:
                pass


class LocalPrintBridgeHandler(BaseHTTPRequestHandler):
    server_version = "ABLocalPrintBridge/1.0"

    def _write_json(self, status_code, payload):
        body = _json_bytes(payload)
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        content_length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(content_length) if content_length > 0 else b"{}"
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def do_OPTIONS(self):
        self._write_json(200, {"ok": True})

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            self._write_json(200, {"ok": True, "service": "ab_sales_local_print_bridge"})
            return
        if path == "/printers":
            printers, default_name = list_printers()
            self._write_json(
                200,
                {
                    "ok": True,
                    "printers": printers,
                    "default_printer": default_name,
                },
            )
            return
        self._write_json(404, {"ok": False, "error": "Not found."})

    def do_POST(self):
        path = urlparse(self.path).path
        payload = self._read_json()
        try:
            if path == "/print_text":
                print_text(
                    payload.get("content", ""),
                    payload.get("printer_name", ""),
                )
                self._write_json(200, {"ok": True})
                return
            if path == "/print_html":
                print_html(
                    payload.get("html", ""),
                    payload.get("printer_name", ""),
                )
                self._write_json(200, {"ok": True})
                return
            self._write_json(404, {"ok": False, "error": "Not found."})
        except Exception as exc:
            self._write_json(400, {"ok": False, "error": str(exc)})

    def log_message(self, fmt, *args):
        return


def main():
    parser = argparse.ArgumentParser(description="AB Sales local printer bridge.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host. Default: 127.0.0.1")
    parser.add_argument("--port", type=int, default=19100, help="Bind port. Default: 19100")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), LocalPrintBridgeHandler)
    print(f"AB Sales Local Print Bridge listening on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
