"""Restrict mail mutations only for the QA Area Manager read-only role."""
from odoo import api, models


def _check_qa_mail_mutation(records, vals_list=()):
    visits = records.env["ab_quality_assurance_visit"]
    if not visits._is_area_manager_read_only():
        return
    field = "model" if records._name == "mail.message" else "res_model"
    # Check both the current and destination document, including batch operations.
    models_used = set(records.sudo().mapped(field))
    default_fields = [field]
    if "res_model_id" in records._fields:
        default_fields.append("res_model_id")
    defaults = records.default_get(default_fields) if vals_list and not records else {}
    for vals in vals_list:
        models_used.add(vals.get(field, defaults.get(field)))
        if field == "res_model" and vals.get("res_model_id", defaults.get("res_model_id")):
            models_used.add(records.env["ir.model"].sudo().browse(
                vals.get("res_model_id", defaults.get("res_model_id"))
            ).model)
    if "ab_quality_assurance_visit" in models_used:
        visits._check_area_manager_chatter_access()


class AbQualityAssuranceMailMessage(models.Model):
    _inherit = "mail.message"

    def _message_reaction(self, content, action, partner, guest, store=None):
        _check_qa_mail_mutation(self)
        return super()._message_reaction(content, action, partner, guest, store=store)

    @api.model_create_multi
    def create(self, vals_list):
        _check_qa_mail_mutation(self.browse(), vals_list)
        return super().create(vals_list)

    def write(self, vals):
        _check_qa_mail_mutation(self, [vals])
        return super().write(vals)

    def unlink(self):
        _check_qa_mail_mutation(self)
        return super().unlink()


class AbQualityAssuranceMailFollowers(models.Model):
    _inherit = "mail.followers"

    @api.model_create_multi
    def create(self, vals_list):
        _check_qa_mail_mutation(self.browse(), vals_list)
        return super().create(vals_list)

    def write(self, vals):
        _check_qa_mail_mutation(self, [vals])
        return super().write(vals)

    def unlink(self):
        _check_qa_mail_mutation(self)
        return super().unlink()


class AbQualityAssuranceMailActivity(models.Model):
    _inherit = "mail.activity"

    @api.model_create_multi
    def create(self, vals_list):
        _check_qa_mail_mutation(self.browse(), vals_list)
        return super().create(vals_list)

    def write(self, vals):
        _check_qa_mail_mutation(self, [vals])
        return super().write(vals)

    def unlink(self):
        _check_qa_mail_mutation(self)
        return super().unlink()

    def _action_done(self, feedback=False, attachment_ids=None):
        # Core posts completion messages with sudo before writing/unlinking.
        _check_qa_mail_mutation(self)
        return super()._action_done(feedback=feedback, attachment_ids=attachment_ids)
