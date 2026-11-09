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
    has_working_balance = fields.Boolean(default=False)
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

    _ab_store_name_unique = models.Constraint('unique(name)', 'NAME CAN NOT BE DUPLICATED.')
    _ab_store_code_unique = models.Constraint('unique(code)', 'CODE CAN NOT BE DUPLICATED.')

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        args = list(args or [])
        code_args = args + [('code', '=', name), ]
        ids = (self.with_user(name_get_uid) if name_get_uid else self).search(code_args, limit=limit).ids
        if not ids:
            args += [('name', operator, name), ]
            ids = (self.with_user(name_get_uid) if name_get_uid else self).search(args, limit=limit).ids
        return ids

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        """Expose the existing search order through the Odoo 19 public API."""
        ids = self._name_search(name, args=domain, operator=operator, limit=limit)
        return [(record.id, record.display_name) for record in self.browse(ids)]

    @api.model
    def _search_display_name(self, operator, value):
        """Keep code/barcode/name matching in relational search domains too."""
        if operator in ('in', 'not in') and isinstance(value, (list, tuple)):
            domain = fields.Domain.OR(self._search_display_name('=', item) for item in value)
            return list(~domain if operator == 'not in' else domain)
        ids = self._name_search(value or '', operator=operator, limit=None)
        return [('id', 'in', ids)]

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
