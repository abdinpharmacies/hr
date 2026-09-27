import logging

from odoo import models


_logger = logging.getLogger(__name__)


class MailTemplate(models.Model):
    _inherit = "mail.template"

    def _ab_storefront_record_ids_without_customer_pdfs(self, res_ids):
        if self.model not in ("sale.order", "ab.prescription.order"):
            return set()
        records = self.env[self.model].browse(res_ids).exists()
        return set(records.filtered("website_id").ids)

    def _ab_is_pdf_attachment(self, attachment):
        return (
            attachment.mimetype == "application/pdf"
            or (attachment.name or "").lower().endswith(".pdf")
        )

    def _ab_remove_customer_pdf_values(self, values):
        before_count = len(values.get("attachments", [])) + len(values.get("attachment_ids", []))
        values["attachments"] = [
            (name, content)
            for name, content in values.get("attachments", [])
            if not (name or "").lower().endswith(".pdf")
        ]
        if values.get("attachment_ids"):
            values["attachment_ids"] = [
                attachment_id
                for attachment_id in values["attachment_ids"]
                if not self._ab_is_pdf_attachment(self.env["ir.attachment"].sudo().browse(attachment_id))
            ]
        return before_count - len(values.get("attachments", [])) - len(values.get("attachment_ids", []))

    def _generate_template_attachments(self, res_ids, render_fields, render_results=None):
        protected_record_ids = self._ab_storefront_record_ids_without_customer_pdfs(res_ids)
        if protected_record_ids and "report_template_ids" in render_fields:
            render_fields = tuple(
                field for field in render_fields if field != "report_template_ids"
            )

        render_results = super()._generate_template_attachments(
            res_ids,
            render_fields,
            render_results=render_results,
        )
        if not protected_record_ids:
            return render_results

        removed_count = 0
        for res_id in protected_record_ids:
            values = render_results.get(res_id)
            if values:
                # Keep PDF reports available in Odoo, but do not attach them to customer messages.
                removed_count += self._ab_remove_customer_pdf_values(values)
        if removed_count:
            _logger.info(
                "Removed %s PDF attachment(s) from storefront customer mail template.",
                removed_count,
            )
        return render_results
