import logging

from odoo import api, models


_logger = logging.getLogger(__name__)


class MailComposeMessage(models.TransientModel):
    _inherit = "mail.compose.message"

    def _ab_prescriptions_to_advance_after_first_message(self):
        template = self.env.ref(
            "ab_ecommerce_storefront.mail_template_prescription_request_received",
            raise_if_not_found=False,
        )
        prescriptions = self.env["ab.prescription.order"]
        for composer in self:
            if composer.model != "sale.order" or not template or composer.template_id != template:
                continue
            orders = self.env["sale.order"].browse(composer._evaluate_res_ids() or []).exists()
            prescriptions |= orders.mapped("ab_prescription_order_ids").filtered(
                lambda prescription: prescription.website_id
                and prescription.state in ("new", "under_review")
            )
        return prescriptions

    def _ab_storefront_record_ids_without_customer_pdfs(self, res_ids):
        if self.model not in ("sale.order", "ab.prescription.order"):
            return set()
        records = self.env[self.model].browse(res_ids).exists()
        return set(records.filtered("website_id").ids)

    @api.depends("composition_mode", "model", "res_domain", "res_ids", "template_id")
    def _compute_attachment_ids(self):
        super()._compute_attachment_ids()
        for composer in self:
            res_ids = composer._evaluate_res_ids() or []
            if not composer._ab_storefront_record_ids_without_customer_pdfs(res_ids):
                continue
            pdf_attachments = composer.attachment_ids.filtered(
                lambda attachment: composer._ab_is_pdf_attachment(attachment)
            )
            if pdf_attachments:
                composer.attachment_ids = composer.attachment_ids - pdf_attachments

    def _ab_is_pdf_attachment(self, attachment):
        return (
            attachment.mimetype == "application/pdf"
            or (attachment.name or "").lower().endswith(".pdf")
        )

    def _ab_filter_pdf_attachment_commands(self, commands):
        if not commands:
            return commands

        attachment_ids = set()
        for command in commands:
            if isinstance(command, int):
                attachment_ids.add(command)
            elif isinstance(command, (list, tuple)) and len(command) >= 2:
                if command[0] in (1, 2, 3, 4) and command[1]:
                    attachment_ids.add(command[1])
                elif command[0] == 6 and len(command) >= 3:
                    attachment_ids.update(command[2] or [])

        pdf_attachment_ids = set(
            self.env["ir.attachment"]
            .sudo()
            .browse(attachment_ids)
            .exists()
            .filtered(lambda attachment: self._ab_is_pdf_attachment(attachment))
            .ids
        )
        if not pdf_attachment_ids:
            return commands

        filtered_commands = []
        for command in commands:
            if isinstance(command, int):
                if command not in pdf_attachment_ids:
                    filtered_commands.append(command)
            elif isinstance(command, (list, tuple)) and len(command) >= 2:
                if command[0] == 0 and len(command) >= 3:
                    values = command[2] or {}
                    if (
                        values.get("mimetype") == "application/pdf"
                        or (values.get("name") or "").lower().endswith(".pdf")
                    ):
                        continue
                if command[0] in (1, 2, 3, 4) and command[1] in pdf_attachment_ids:
                    continue
                if command[0] == 6 and len(command) >= 3:
                    filtered_commands.append(
                        (
                            command[0],
                            command[1],
                            [att_id for att_id in (command[2] or []) if att_id not in pdf_attachment_ids],
                        )
                    )
                else:
                    filtered_commands.append(command)
            else:
                filtered_commands.append(command)
        return filtered_commands

    def _ab_remove_customer_pdf_values(self, mail_values):
        mail_values["attachments"] = [
            (name, content)
            for name, content in mail_values.get("attachments", [])
            if not (name or "").lower().endswith(".pdf")
        ]
        if "attachment_ids" in mail_values:
            mail_values["attachment_ids"] = self._ab_filter_pdf_attachment_commands(
                mail_values["attachment_ids"]
            )

    def _generate_template_for_composer(
        self,
        res_ids,
        render_fields,
        allow_suggested=False,
        find_or_create_partners=True,
    ):
        protected_record_ids = self._ab_storefront_record_ids_without_customer_pdfs(res_ids)
        guarded_fields = tuple(
            field
            for field in render_fields
            if field not in ("attachments", "report_template_ids")
        )
        active_render_fields = guarded_fields if protected_record_ids else render_fields

        values = super()._generate_template_for_composer(
            res_ids,
            active_render_fields,
            allow_suggested=allow_suggested,
            find_or_create_partners=find_or_create_partners,
        )
        if not protected_record_ids:
            return values

        for res_id in protected_record_ids:
            if res_id in values:
                # Keep PDF reports available in Odoo, but do not attach them to customer messages.
                self._ab_remove_customer_pdf_values(values[res_id])
        return values

    def _prepare_mail_values(self, res_ids):
        values = super()._prepare_mail_values(res_ids)
        protected_record_ids = self._ab_storefront_record_ids_without_customer_pdfs(res_ids)
        if not protected_record_ids:
            return values

        removed_count = 0
        for res_id in protected_record_ids:
            mail_values = values.get(res_id)
            if not mail_values:
                continue
            before_count = len(mail_values.get("attachments", [])) + len(
                mail_values.get("attachment_ids", [])
            )
            self._ab_remove_customer_pdf_values(mail_values)
            after_count = len(mail_values.get("attachments", [])) + len(
                mail_values.get("attachment_ids", [])
            )
            removed_count += max(before_count - after_count, 0)
        if removed_count:
            _logger.info(
                "Removed %s PDF attachment(s) from storefront customer message(s).",
                removed_count,
            )
        return values

    def action_send_mail(self):
        prescriptions_to_advance = self._ab_prescriptions_to_advance_after_first_message()
        result = super().action_send_mail()
        if prescriptions_to_advance:
            prescriptions_to_advance.action_waiting_call_center()
        return result
