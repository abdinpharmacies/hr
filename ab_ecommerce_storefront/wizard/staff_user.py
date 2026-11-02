from copy import deepcopy

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
    login_from_anywhere = fields.Boolean(string="Login From Anywhere", readonly=True, default=True)
    group_ids = fields.Many2many(
        "res.groups",
        string="Access Rights",
        default=lambda self: self.env.ref("base.group_user"),
    )
    view_group_hierarchy = fields.Json(
        default=lambda self: self._default_staff_group_hierarchy(),
    )

    @api.model
    def _default_staff_group_hierarchy(self):
        hierarchy = deepcopy(self.env["res.groups"].sudo()._get_view_group_hierarchy())
        protected_id = self.env.ref("ab_store.ab_login_from_anywhere").id
        hierarchy["groups"].pop(protected_id, None)
        for group in hierarchy["groups"].values():
            for key in ("disjoint_ids", "implied_ids", "all_implied_ids", "all_implied_by_ids"):
                group[key] = [group_id for group_id in group[key] if group_id != protected_id]
        for privilege in hierarchy["privileges"].values():
            privilege["group_ids"] = [group_id for group_id in privilege["group_ids"] if group_id != protected_id]
        for category in hierarchy["categories"]:
            category["privilege_ids"] = [
                privilege_id for privilege_id in category["privilege_ids"]
                if hierarchy["privileges"][privilege_id]["group_ids"]
            ]
        return hierarchy

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        account_id = self.env.context.get("default_account_id")
        if account_id:
            account = self.env["ab_ecommerce_staff_account"].browse(account_id)
            account._check_manage_access()
            target = account.user_id.sudo()
            values.update({
                "account_id": account.id,
                "name": target.name,
                "login": target.login,
                "email": target.email,
                "active": target.active,
                "group_ids": [fields.Command.set(target.group_ids.ids)],
                "login_from_anywhere": self.env.ref("ab_store.ab_login_from_anywhere") in target.group_ids,
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
        internal = self.env.ref("base.group_user")
        portal = self.env.ref("base.group_portal")
        public = self.env.ref("base.group_public")
        groups = self.group_ids.sudo()
        if portal in groups.all_implied_ids or public in groups.all_implied_ids:
            raise ValidationError(_("Only internal employee accounts can be managed here."))
        groups |= internal
        login_anywhere = self.env.ref("ab_store.ab_login_from_anywhere")
        values = {
            "name": name,
            "login": login,
            "email": email,
            "active": self.active,
        }
        if self.account_id:
            account = self.account_id
            account._check_manage_access()
            target = account.user_id.sudo()
            groups -= login_anywhere
            if login_anywhere in target.group_ids:
                groups |= login_anywhere
            values["group_ids"] = [fields.Command.set(groups.ids)]
            target.write(values)
        else:
            company = self.env.company
            if company not in actor.company_ids:
                raise AccessError(_("You cannot create a staff user for this company."))
            values.update({
                "company_id": company.id,
                "company_ids": [fields.Command.set(company.ids)],
                "group_ids": [fields.Command.set((groups | login_anywhere).ids)],
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
