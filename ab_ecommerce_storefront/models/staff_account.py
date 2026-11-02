from odoo import _, fields, models
from odoo.exceptions import AccessError


class StaffAccount(models.Model):
    _name = "ab_ecommerce_staff_account"
    _description = "Website Staff Account"
    _rec_name = "name"

    user_id = fields.Many2one("res.users", required=True, readonly=True, ondelete="restrict")
    owner_id = fields.Many2one("res.users", required=True, readonly=True, ondelete="restrict")
    company_id = fields.Many2one("res.company", required=True, readonly=True)
    name = fields.Char(related="user_id.name")
    login = fields.Char(related="user_id.login")
    email = fields.Char(related="user_id.email")
    user_active = fields.Boolean(related="user_id.active", string="Active")
    access_role = fields.Selection(
        [
            ("employee", "Employee"),
            ("website_editor", "Website Editor"),
            ("website_designer", "Website Editor and Designer"),
            ("administrator", "Administrator"),
        ],
        compute="_compute_access_role",
        string="Access Rights",
    )

    def _compute_access_role(self):
        administrator = self.env.ref("base.group_system")
        designer = self.env.ref("website.group_website_designer")
        editor = self.env.ref("website.group_website_restricted_editor")
        for account in self:
            groups = account.user_id.sudo().group_ids
            account.access_role = (
                "administrator" if administrator in groups else
                "website_designer" if designer in groups else
                "website_editor" if editor in groups else "employee"
            )

    def _check_manage_access(self):
        actor = self.env.user
        if not actor.has_group("website.group_website_designer"):
            raise AccessError(_("Only Website editors can manage staff users here."))
        for account in self:
            if account.owner_id != actor or account.company_id not in actor.company_ids:
                raise AccessError(_("You can manage only staff users you created in your companies."))
            target = account.user_id.sudo()
            if (
                target.share
                or account.company_id not in target.company_ids
                or not set(target.company_ids.ids).issubset(set(actor.company_ids.ids))
            ):
                raise AccessError(_("This account cannot be managed from this screen."))

    def action_edit_user(self):
        self.ensure_one()
        self._check_manage_access()
        return {
            "type": "ir.actions.act_window",
            "name": _("Edit Staff User"),
            "res_model": "ab_ecommerce_staff_user_wizard",
            "view_mode": "form",
            "view_id": self.env.ref("ab_ecommerce_storefront.view_staff_user_wizard_form").id,
            "target": "new",
            "context": {"default_account_id": self.id},
        }

    def action_send_password_link(self):
        self.ensure_one()
        self._check_manage_access()
        target = self.user_id.sudo()
        return target.with_context(create_user=not bool(target.login_date)).action_reset_password()
