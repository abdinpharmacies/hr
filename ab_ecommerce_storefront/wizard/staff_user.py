from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


class StaffUserWizard(models.TransientModel):
    _name = "ab_ecommerce_staff_user_wizard"
    _description = "Create Website Staff User"

    name = fields.Char(required=True)
    login = fields.Char(required=True)
    email = fields.Char(required=True)
    account_id = fields.Many2one("ab_ecommerce_staff_account", readonly=True)
    active = fields.Boolean(default=True)
    new_password = fields.Char(string="New Password", copy=False)
    confirm_password = fields.Char(string="Confirm Password", copy=False)
    access_role = fields.Selection(
        [
            ("employee", "Employee"),
            ("website_editor", "Website Editor"),
            ("website_designer", "Website Editor and Designer"),
        ],
        string="Access Rights",
        required=True,
        default="employee",
    )

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        account_id = self.env.context.get("default_account_id")
        if account_id:
            account = self.env["ab_ecommerce_staff_account"].browse(account_id)
            account._check_manage_access()
            target = account.user_id.sudo()
            role = account.access_role
            values.update({
                "account_id": account.id,
                "name": target.name,
                "login": target.login,
                "email": target.email,
                "active": target.active,
                "access_role": role,
            })
        return values

    def action_create_user(self):
        return self.action_save_user()

    def action_save_user(self):
        self.ensure_one()
        actor = self.env.user
        if not actor.has_group("website.group_website_designer"):
            raise AccessError(_("Only Website editors can manage staff users here."))
        name = (self.name or "").strip()
        login = (self.login or "").strip()
        email = (self.email or "").strip()
        if not name or not login or not email:
            raise ValidationError(_("Name, login, and email are required."))
        if self.new_password or self.confirm_password:
            if self.new_password != self.confirm_password:
                raise ValidationError(_("The passwords do not match."))
            if len(self.new_password) < 12:
                raise ValidationError(_("Password must be at least 12 characters."))
        group_by_role = {
            "employee": self.env.ref("base.group_user"),
            "website_editor": self.env.ref("website.group_website_restricted_editor"),
            "website_designer": self.env.ref("website.group_website_designer"),
        }
        if self.access_role not in group_by_role:
            raise ValidationError(_("Select a permitted access role."))
        groups = self.env.ref("base.group_user") | group_by_role[self.access_role]
        values = {
            "name": name,
            "login": login,
            "email": email,
            "active": self.active,
            "group_ids": [fields.Command.set(groups.ids)],
        }
        if self.account_id:
            account = self.account_id
            account._check_manage_access()
            target = account.user_id.sudo()
            target.write(values)
        else:
            company = self.env.company
            if company not in actor.company_ids:
                raise AccessError(_("You cannot create a staff user for this company."))
            values.update({
                "company_id": company.id,
                "company_ids": [fields.Command.set(company.ids)],
            })
            target = self.env["res.users"].sudo().with_company(company).with_context(
                no_reset_password=bool(self.new_password)
            ).create(values)
            self.env["ab_ecommerce_staff_account"].sudo().create({
                "user_id": target.id,
                "owner_id": actor.id,
                "company_id": company.id,
            })
        if self.new_password:
            target._change_password(self.new_password)
        invitation_failed = not self.account_id and not self.new_password and not target.partner_id.signup_type
        action = self.env.ref("ab_ecommerce_storefront.action_staff_accounts").sudo().read()[0]
        self.sudo().unlink()
        if invitation_failed:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Staff user created"),
                    "message": _("No invitation email was sent. Check outgoing email, then use Send Password Link."),
                    "type": "warning",
                    "sticky": True,
                    "next": action,
                },
            }
        return action
