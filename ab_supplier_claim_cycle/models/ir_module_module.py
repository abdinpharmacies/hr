from odoo import api, models


class IrModuleModule(models.Model):
    _inherit = 'ir.module.module'

    @api.model
    def _supplier_claim_install_extension_modules(self):
        modules = self.sudo().search([
            ('name', 'in', [
                'ab_supplier_claim_workflow',
                'ab_supplier_claim_workflow_telegram',
            ]),
            ('state', '=', 'uninstalled'),
        ])
        if modules:
            modules.button_install()
        return True
