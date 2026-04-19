from odoo.tests.common import TransactionCase


class TestAbSmartSecurityManager(TransactionCase):
    def test_role_creation_creates_group_and_acl(self):
        model = self.env["ir.model"].search([("model", "=", "res.partner")], limit=1)
        role = self.env["ab_security_role"].create({"name": "Partner Viewer"})
        self.env["ab_security_model_access"].create(
            {
                "role_id": role.id,
                "model_id": model.id,
                "perm_read": True,
                "perm_write": False,
                "perm_create": False,
                "perm_unlink": False,
                "active": True,
            }
        )
        access = self.env["ir.model.access"].sudo().search(
            [("ab_security_model_access_id.role_id", "=", role.id)],
            limit=1,
        )
        self.assertTrue(role.group_id)
        self.assertTrue(access)

    def test_copy_user_permissions_assigns_role(self):
        group_user = self.env.ref("base.group_user")
        role = self.env["ab_security_role"].create({"name": "Copied Role"})
        source_user = self.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "Source Security User",
                "login": "source_security_user",
                "email": "source_security_user@example.com",
                "group_ids": [(6, 0, [group_user.id])],
                "ab_role_ids": [(6, 0, [role.id])],
            }
        )
        target_user = self.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "Target Security User",
                "login": "target_security_user",
                "email": "target_security_user@example.com",
                "group_ids": [(6, 0, [group_user.id])],
            }
        )
        self.env["ab_security_role"].copy_user_permissions(source_user.id, target_user.id)
        self.assertIn(role, target_user.ab_role_ids)

    def test_role_assignment_syncs_managed_groups_only(self):
        group_user = self.env.ref("base.group_user")
        preserved_group = self.env.ref("base.group_partner_manager")
        role = self.env["ab_security_role"].create({"name": "Managed Group Sync"})
        user = self.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "Managed Group User",
                "login": "managed_group_user",
                "email": "managed_group_user@example.com",
                "group_ids": [(6, 0, [group_user.id, preserved_group.id])],
            }
        )

        user.write({"ab_role_ids": [(4, role.id)]})
        self.assertIn(role.group_id, user.group_ids)
        self.assertIn(preserved_group, user.group_ids)

        user.write({"ab_role_ids": [(3, role.id)]})
        self.assertNotIn(role.group_id, user.group_ids)
        self.assertIn(preserved_group, user.group_ids)
