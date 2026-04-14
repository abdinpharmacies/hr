from odoo import api, fields, models


class Store(models.Model):
    _name = 'ab_store'
    _description = 'Store'

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    status = fields.Selection(selection=[('internal', 'Internal'),
                                         ('external', 'External')],
                              default='internal')
    store_type = fields.Selection(selection=[('main', 'Main'),
                                             ('branch', 'Branch'),
                                             ('store', 'Store'),
                                             ('internal_store', 'Internal Store'), ],
                                  default='branch')
    location = fields.Char()
    telephone = fields.Char()
    active = fields.Boolean(default=True)
    allow_purchase = fields.Boolean(default=True)
    allow_sale = fields.Boolean(default=True)
    allow_transfer = fields.Boolean(default=True)
    allow_replication = fields.Boolean(default=True)
    ip1 = fields.Char()
    ip2 = fields.Char()
    ip3 = fields.Char()
    ip4 = fields.Char()

    store_ips = fields.One2many('ab_store_ip', 'store_id', string="IPs")
    parent_id = fields.Many2one('ab_store')
    last_update_date = fields.Datetime()
    max_trans_value = fields.Float()

    @api.model
    def _search_display_name(self, operator, value):
        code_ids = self._search([('code', '=', value)])
        if code_ids:
            return [('id', 'in', code_ids)]
        return [('name', operator, value)]

    def write(self, values):
        res = super().write(values)
        StoreIP = self.env['ab_store_ip'].sudo()
        for rec in self:
            data = rec.read(['ip1', 'ip2', 'ip3', 'ip4'])
            ips = data[0].copy() if data else {}
            ips.pop('id', None)
            for ip in ips.values():
                if ip and not StoreIP.search([('name', '=', ip)], limit=1):
                    StoreIP.create({'name': ip, 'store_id': rec.id, 'include': True})
        return res
