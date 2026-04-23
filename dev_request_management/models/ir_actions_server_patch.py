# -*- coding: utf-8 -*-
import re

from odoo import api, models


class IrActionsServer(models.Model):
    _inherit = "ir.actions.server"

    @api.model
    def _register_hook(self):
        result = super()._register_hook()
        self._patch_totp_invite_actions()
        return result

    @api.model
    def _patch_totp_invite_actions(self):
        actions = self.sudo().search(
            [
                ("state", "=", "code"),
                ("code", "ilike", "records.action_"),
            ]
        )
        for action in actions:
            code = action.code or ""
            patched = re.sub(
                r"\brecords\.(action_[A-Za-z0-9_]+)\(\)",
                r"(records or env.user).\1()",
                code,
            )
            if patched != code:
                action.write({"code": patched})
