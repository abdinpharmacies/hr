from odoo import _, fields, models
from odoo.exceptions import AccessError, ValidationError


class StaffUserWizard(models.TransientModel):
    _name = "ab_ecommerce_staff_user_wizard"
    _description = "Create Website Staff User"

    name = fields.Char(required=True)
    login = fields.Char(required=True)
    email = fields.Char(required=True)

    def action_create_user(self):
        self.ensure_one()
        user = self.env.user
        if not user.has_group("website.group_website_designer"):
            raise AccessError(_("Only Website editors can create staff users here."))
        company = self.env.company
        if company not in user.company_ids:
            raise AccessError(_("You cannot create a staff user for this company."))
        name = (self.name or "").strip()
        login = (self.login or "").strip()
        email = (self.email or "").strip()
        if not name or not login or not email:
            raise ValidationError(_("Name, login, and email are required."))
        employee_group = self.env.ref("base.group_user")
        self.env["res.users"].sudo().with_company(company).create({
            "name": name,
            "login": login,
            "email": email,
            "company_id": company.id,
            "company_ids": [fields.Command.set(company.ids)],
            "group_ids": [fields.Command.set(employee_group.ids)],
        })
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Staff user created"),
                "message": _("An invitation email will be sent if mail delivery is available."),
                "type": "success",
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
