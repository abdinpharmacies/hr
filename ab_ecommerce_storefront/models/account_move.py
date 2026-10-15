from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _get_mail_template(self):
        template = super()._get_mail_template()
        if self and all(move.website_id for move in self):
            return self.env.ref("ab_ecommerce_storefront.mail_template_invoice_order_stage")
        return template

    def _ab_storefront_message_orders(self):
        self.ensure_one()
        return self.invoice_line_ids.sale_line_ids.order_id.filtered(
            lambda order: order.website_id == self.website_id
            and order.company_id == self.company_id
        )

    def _notify_by_email_prepare_rendering_context(
        self, message, msg_vals=False, model_description=False,
        force_email_company=False, force_email_lang=False, force_record_name=False,
    ):
        values = super()._notify_by_email_prepare_rendering_context(
            message, msg_vals=msg_vals, model_description=model_description,
            force_email_company=force_email_company, force_email_lang=force_email_lang,
            force_record_name=force_record_name,
        )
        invoice = values["record"]
        if invoice.website_id:
            orders = invoice._ab_storefront_message_orders()
            values["record_name"] = ", ".join(
                order._ab_storefront_display_reference() for order in orders
            ) or invoice.env._("Order status update")
            values["subtitles"] = [values["record_name"]]
            values["model_description"] = invoice.env._("Order status update")
        return values
