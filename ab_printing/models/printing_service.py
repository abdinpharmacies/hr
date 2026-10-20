import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PrintingService(models.AbstractModel):
    _name = 'ab_printing_service'
    _description = 'Printing Service'

    @api.model
    def print_report(self, report_xmlid, records, printer, copies=1):
        """Python API for business buttons; records must be an Odoo recordset."""
        if not isinstance(records, models.BaseModel) or not records:
            raise UserError(_("Select records to print."))
        records = self.env[records._name].browse(records.ids)
        records.check_access('read')
        report = self.env.ref(report_xmlid)
        if report._name != 'ir.actions.report' or report.model != records._name:
            raise UserError(_("The report does not match the selected records."))
        report.check_access('read')
        if report.group_ids and not (report.group_ids & self.env.user.all_group_ids):
            raise UserError(_("You do not have access to this report."))
        server, queue = self._destination(printer, copies)
        pdf, output_type = self.env['ir.actions.report'].with_context(
            report_pdf_no_attachment=True,
        )._render_qweb_pdf(report_xmlid, res_ids=records.ids)
        return self._submit_pdf(pdf, server, queue, copies)

    def _command(self, args, timeout=30):
        binary = shutil.which(args[0])
        if not binary:
            raise UserError(_("Required printing command is missing: %s", args[0]))
        try:
            result = subprocess.run(
                [binary, *args[1:]], capture_output=True, text=True,
                encoding='utf-8', errors='replace', timeout=timeout,
                check=False, env=dict(os.environ, LC_ALL='C'),
            )
        except subprocess.TimeoutExpired as error:
            raise UserError(_("Printing timed out. Check CUPS jobs before retrying to avoid duplicate printing.")) from error
        except OSError as error:
            raise UserError(_("Could not execute the printing command.")) from error
        if result.returncode:
            _logger.warning('Printing command failed: command=%s status=%s', args[0], result.returncode)
            raise UserError(_("Printing command failed. Check the printer configuration and CUPS jobs before retrying."))
        return result.stdout

    @api.model
    def list_printers(self):
        """Read configured CUPS queues without creating printer records."""
        output = self._command(['lpstat', '-h', self._server(), '-p'])
        return sorted(set(re.findall(r'^printer (\S+) ', output, re.MULTILINE)))

    def _server(self):
        server = self.env['ir.config_parameter'].sudo().get_param(
            'ab_printing.server', 'localhost:631',
        ).strip()
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]*(?::[0-9]{1,5})?', server):
            raise UserError(_("Configure a valid CUPS server in ab_printing.server."))
        return server

    def _destination(self, printer, copies):
        queue = str(printer or '').strip()
        server = self._server()
        if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*', queue):
            raise UserError(_("Select a valid CUPS queue name."))
        if type(copies) is not int or not 1 <= copies <= 99:
            raise UserError(_("Copies must be an integer between 1 and 99."))
        options = self._command(['lpoptions', '-h', server, '-p', queue])
        if 'raw printer' in options.lower() or "printer-make-and-model='raw'" in options.lower():
            raise UserError(_("This queue requires raw printer data. Select a PDF-capable CUPS queue."))
        return server, queue

    def _print_html(self, html_content, printer, print_format='a4', copies=1):
        """Trusted server-generated HTML only; deliberately unavailable over RPC."""
        server, queue = self._destination(printer, copies)
        if not html_content or print_format not in ('a4', 'pos_80mm'):
            raise UserError(_("Provide receipt content and a supported paper format."))
        with tempfile.TemporaryDirectory(prefix='ab_printing_') as directory:
            source = Path(directory) / 'receipt.html'
            document = Path(directory) / 'receipt.pdf'
            source.write_text(html_content, encoding='utf-8')
            paper = ['--page-size', 'A4'] if print_format == 'a4' else [
                '--page-width', '80mm', '--page-height', '297mm',
            ]
            self._command([
                'wkhtmltopdf', '--quiet', '--encoding', 'utf-8',
                '--disable-local-file-access', *paper,
                '--margin-top', '0', '--margin-bottom', '0',
                '--margin-left', '0', '--margin-right', '0',
                str(source), str(document),
            ], timeout=60)
            return self._submit_pdf(document.read_bytes(), server, queue, copies)

    def _submit_pdf(self, pdf, server, queue, copies):
        if not isinstance(pdf, bytes) or not pdf.startswith(b'%PDF-'):
            raise UserError(_("Could not generate a valid PDF for printing."))
        with tempfile.TemporaryDirectory(prefix='ab_printing_') as directory:
            document = Path(directory) / 'document.pdf'
            document.write_bytes(pdf)
            output = self._command([
                'lp', '-h', server, '-d', queue, '-n', str(copies), str(document),
            ])
        match = re.search(r'request id is (\S+)', output)
        if not match:
            raise UserError(_("CUPS returned no job ID. Check its jobs before retrying to avoid duplicate printing."))
        job_id = match.group(1)
        _logger.info('Print submitted: db=%s user=%s queue=%s job=%s',
                     self.env.cr.dbname, self.env.uid, queue, job_id)
        return {'ok': True, 'printer_name': queue, 'job_id': job_id}
