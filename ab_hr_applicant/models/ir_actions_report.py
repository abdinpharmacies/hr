import re

from markupsafe import Markup

from odoo import api, models

AB_HR_APPLICATION_REPORT_NAME = "ab_hr_applicant.report_ab_hr_application"
ASSET_LINK_RE = re.compile(r"""<link[^>]*href=['"]/web/assets/[^>]*>""", flags=re.IGNORECASE)
SCRIPT_TAG_RE = re.compile(
    r"""<script\b[^<]*(?:(?!</script>)<[^<]*)*</script>""",
    flags=re.IGNORECASE | re.DOTALL,
)
BASE_TAG_RE = re.compile(r"""<base[^>]*>""", flags=re.IGNORECASE)


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _force_report_lang(self, report_ref):
        report = self._get_report(report_ref)
        if report.report_name == AB_HR_APPLICATION_REPORT_NAME and self.env.context.get("lang") != "ar_001":
            return self.with_context(lang="ar_001")
        return self

    @staticmethod
    def _sanitize_report_html(body):
        body = str(body)
        body = BASE_TAG_RE.sub("", body)
        body = ASSET_LINK_RE.sub("", body)
        body = SCRIPT_TAG_RE.sub("", body)
        return Markup(body)

    @api.model
    def _render_qweb_html(self, report_ref, docids, data=None):
        return super(IrActionsReport, self._force_report_lang(report_ref))._render_qweb_html(
            report_ref, docids, data=data
        )

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        return super(IrActionsReport, self._force_report_lang(report_ref))._render_qweb_pdf(
            report_ref, res_ids=res_ids, data=data
        )

    def _prepare_html(self, html, report_model=False):
        result = super()._prepare_html(html, report_model=report_model)
        if not result:
            return result

        bodies, res_ids, header, footer, specific_paperformat_args = result
        if self.report_name == AB_HR_APPLICATION_REPORT_NAME:
            # Keep this report independent from external bundles to reduce wkhtmltopdf
            # crashes on unpatched Qt builds.
            bodies = [self._sanitize_report_html(body) for body in bodies]
            header = False
            footer = False
        return bodies, res_ids, header, footer, specific_paperformat_args
