from odoo import api, fields, models
from odoo.tools.translate import _


class AbStoreIp(models.Model):
    _name = 'ab_store_ip'
    _description = 'ab_store_ip'

    name = fields.Char(string="IP", index=True, required=True)
    store_id = fields.Many2one('ab_store', index=True, required=True)
    include = fields.Boolean(default=False, readonly=True)

    def btn_include_exclude(self):
        self.include = not self.include
