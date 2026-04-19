from odoo import Command, _, api, fields, models


class AbSecurityRole(models.Model):
    _name = "ab_security_role"
    _description = "Smart Security Role"
    _order = "name"

    _group_unique = models.Constraint(
        "unique(group_id)",
        "Each security role must be linked to a unique group.",
    )

    active = fields.Boolean(default=True)
    name = fields.Char(required=True)
    group_id = fields.Many2one(
        "res.groups",
        required=True,
        readonly=True,
        ondelete="restrict",
    )
    parent_role_id = fields.Many2one(
        "ab_security_role",
        string="Parent Role",
        ondelete="restrict",
    )
    inherited = fields.Boolean(default=False)
    user_ids = fields.Many2many(
        "res.users",
        "ab_security_role_user_rel",
        "role_id",
        "user_id",
        string="Users",
    )
    model_access_ids = fields.One2many(
        "ab_security_model_access",
        "role_id",
        string="Model Access",
    )
    field_access_ids = fields.One2many(
        "ab_security_field_access",
        "role_id",
        string="Field Access",
    )
    managed_group = fields.Boolean(related="group_id.ab_security_managed")

    @api.model_create_multi
    def create(self, vals_list):
        prepared_vals = []
        for vals in vals_list:
            role_vals = dict(vals)
            if not role_vals.get("group_id") or not self.env.context.get("ab_security_allow_existing_group"):
                parent_role = self.browse(role_vals["parent_role_id"]) if role_vals.get("parent_role_id") else self.browse()
                role_vals["group_id"] = self._create_group_for_role(
                    role_vals.get("name"),
                    parent_role,
                ).id
                if parent_role:
                    role_vals["inherited"] = True
            prepared_vals.append(role_vals)

        roles = super().create(prepared_vals)
        for role, vals in zip(roles, prepared_vals):
            if vals.get("parent_role_id"):
                role.parent_role_id._copy_permissions_to(role)
            role._sync_group_metadata()
        roles.mapped("user_ids")._sync_ab_role_group_membership()
        roles._apply_role_permissions()
        return roles

    def write(self, vals):
        previous_users = self.mapped("user_ids")
        res = super().write(vals)
        for role in self:
            if "name" in vals and role.group_id.ab_security_managed:
                role.group_id.sudo().write({"name": role.name})
            if "parent_role_id" in vals and role.group_id.ab_security_managed:
                implied_commands = []
                if role.parent_role_id:
                    implied_commands.append(Command.link(role.parent_role_id.group_id.id))
                role.group_id.sudo().write({"implied_ids": implied_commands})
                role.inherited = bool(role.parent_role_id)
            role._sync_group_metadata()
        (previous_users | self.mapped("user_ids"))._sync_ab_role_group_membership()
        self._apply_role_permissions()
        return res

    def action_apply_permissions(self):
        self._apply_role_permissions()
        return True

    def action_duplicate_role(self):
        self.ensure_one()
        copied_role = self.copy_role(self.id, _("Copy of %s") % self.name)
        return copied_role._action_open_form()

    def action_inherit_role(self):
        self.ensure_one()
        inherited_role = self.copy_role(self.id, _("Inherited from %s") % self.name)
        return inherited_role._action_open_form()

    def _action_open_form(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "ab_security_role",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    @api.model
    def copy_role(self, source_role_id, new_name):
        source_role = self.browse(source_role_id).exists()
        if not source_role:
            return self.browse()
        new_role = self.create(
            {
                "name": new_name,
                "parent_role_id": source_role.id,
            }
        )
        return new_role

    @api.model
    def copy_user_permissions(self, source_user_id, target_user_id):
        source_user = self.env["res.users"].browse(source_user_id).exists()
        target_user = self.env["res.users"].browse(target_user_id).exists()
        if not source_user or not target_user:
            return False
        commands = [
            Command.link(role.id)
            for role in source_user.ab_role_ids
            if role.id not in target_user.ab_role_ids.ids
        ]
        if commands:
            target_user.write({"ab_role_ids": commands})
        return True

    @api.model
    def apply_role_permissions(self, role_id):
        role = self.browse(role_id).exists()
        if role:
            role._apply_role_permissions()
        return True

    @api.model
    def _bootstrap_existing_roles(self):
        existing_group_ids = set(self.search([]).mapped("group_id").ids)
        groups = self.env["res.groups"].sudo().search([("id", "not in", list(existing_group_ids))])
        for group in groups:
            role = self.with_context(ab_security_allow_existing_group=True).create(
                {
                    "name": group.name,
                    "group_id": group.id,
                }
            )
            role.group_id.sudo().write(
                {
                    "ab_security_managed": group.ab_security_managed,
                    "ab_security_role_id": role.id,
                }
            )
        return True

    def _create_group_for_role(self, role_name, parent_role):
        group_vals = {
            "name": role_name,
            "ab_security_managed": True,
        }
        if parent_role:
            group_vals["implied_ids"] = [Command.link(parent_role.group_id.id)]
        return self.env["res.groups"].sudo().create(group_vals)

    def _copy_permissions_to(self, target_role):
        self.ensure_one()
        model_access_commands = []
        field_access_commands = []
        for access in self.model_access_ids:
            model_access_commands.append(
                Command.create(
                    {
                        "model_id": access.model_id.id,
                        "perm_read": access.perm_read,
                        "perm_write": access.perm_write,
                        "perm_create": access.perm_create,
                        "perm_unlink": access.perm_unlink,
                        "active": access.active,
                    }
                )
            )
        for field_access in self.field_access_ids:
            field_access_commands.append(
                Command.create(
                    {
                        "field_id": field_access.field_id.id,
                        "can_view": field_access.can_view,
                        "can_edit": field_access.can_edit,
                    }
                )
            )
        if model_access_commands:
            target_role.write({"model_access_ids": model_access_commands})
        if field_access_commands:
            target_role.write({"field_access_ids": field_access_commands})

    def _sync_group_metadata(self):
        for role in self:
            role.group_id.sudo().write(
                {
                    "ab_security_role_id": role.id,
                }
            )

    def _ensure_relation_read_permissions(self):
        for role in self:
            for field_access in role.field_access_ids.filtered(lambda line: line.can_view or line.can_edit):
                if field_access.field_type not in ("many2one", "one2many", "many2many"):
                    continue
                if not field_access.relation_model_name:
                    continue
                relation_model = self.env["ir.model"].sudo().search(
                    [("model", "=", field_access.relation_model_name)],
                    limit=1,
                )
                if not relation_model:
                    continue
                existing_access = role.model_access_ids.filtered(
                    lambda line: line.model_id == relation_model and line.active
                )[:1]
                if existing_access:
                    if not existing_access.perm_read:
                        existing_access.write({"perm_read": True})
                    continue
                self.env["ab_security_model_access"].create(
                    {
                        "role_id": role.id,
                        "model_id": relation_model.id,
                        "perm_read": True,
                        "perm_write": False,
                        "perm_create": False,
                        "perm_unlink": False,
                        "active": True,
                    }
                )

    def _apply_role_permissions(self):
        for role in self:
            role.user_ids._sync_ab_role_group_membership()
            role._ensure_relation_read_permissions()
            role.model_access_ids._sync_ir_model_access()
        return True
