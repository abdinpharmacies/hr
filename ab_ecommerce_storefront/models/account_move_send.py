from odoo import api, models
from odoo.tools.mimetypes import guess_mimetype


class AccountMoveSend(models.AbstractModel):
    _inherit = "account.move.send"

    @api.model
    def _get_default_mail_attachments_widget(
        self, move, mail_template, invoice_edi_format=None, extra_edis=None, pdf_report=None,
    ):
        attachments = super()._get_default_mail_attachments_widget(
            move,
            mail_template,
            invoice_edi_format=invoice_edi_format,
            extra_edis=extra_edis,
            pdf_report=pdf_report,
        )
        if move.website_id:
            attachments = [
                attachment for attachment in attachments
                if attachment.get("mimetype") != "application/pdf"
                and not (attachment.get("name") or "").lower().endswith(".pdf")
            ]
        return attachments

    def _send_mail(self, move, mail_template, **kwargs):
        if move.website_id:
            kwargs["attachments"] = [
                attachment for attachment in kwargs.get("attachments", [])
                if not (attachment[0] or "").lower().endswith(".pdf")
                and guess_mimetype(attachment[1]) != "application/pdf"
            ]
            if kwargs.get("attachment_ids"):
                kwargs["attachment_ids"] = self.env[
                    "mail.compose.message"
                ]._ab_filter_pdf_attachment_commands(kwargs["attachment_ids"])
        return super()._send_mail(move, mail_template, **kwargs)
