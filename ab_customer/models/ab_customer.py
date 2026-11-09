import re

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class Customer(models.Model):
    _name = 'ab_customer'
    _description = 'ab_customer'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'eplus_serial desc,id desc'

    code = fields.Char(size=16, required=True, index=True, readonly=True)
    costcenter_id = fields.Many2one('ab_costcenter', index=True)
    name = fields.Char(required=True, index=True, tracking=True)
    mobile_phone = fields.Char('Mobile', index=True, tracking=True)
    work_phone = fields.Char('Tel', index=True, tracking=True)
    delivery_phone = fields.Char('Delivery Phone', index=True, tracking=True)
    address = fields.Char(index=True, tracking=True)
    default_store_id = fields.Many2one('ab_store', index=True, readonly=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    contact_ids = fields.One2many('ab_customer_contact', 'customer_id', string='Contacts')
    phones = fields.Char(compute='_compute_phones')
    customer_search = fields.Char(compute='_compute_customer_search', search='_search_customer_search')

    def _compute_customer_search(self):
        for rec in self:
            rec.customer_search = ""

    def _search_customer_search(self, operator, val):
        self.env.cr.execute(" select id from ab_customer "
                            " where "
                            " name ilike %(val)s"
                            " or mobile_phone ilike %(val)s"
                            " or work_phone ilike %(val)s"
                            " or address ilike %(val)s", {'val': f"%{val.replace(' ', '%')}%"})
        ids = [row[0] for row in self.env.cr.fetchall()]

        return [('id', 'in', ids)]

    def _compute_phones(self):
        for rec in self:
            phones = set()
            if rec.work_phone:
                phones.add(rec.work_phone)
            if rec.mobile_phone:
                phones.add(rec.mobile_phone)
            rec.phones = ','.join(phones)

    @api.constrains('name', 'mobile_phone', 'work_phone', 'address')
    def _check_customer_fields(self):
        for rec in self:
            # Guard condition to ignore all constrains if eplus replication
            if self.env.context.get('eplus_replication'):
                continue

            # --- Name: at least 2 words, each ≥ 2 chars ---
            if rec.name:
                words = rec.name.strip().split()
                if len(words) < 2 and any(len(w) < 2 for w in words):
                    raise ValidationError(
                        "Name must contain at least two words, each with at least 2 characters."
                    )
            else:
                raise ValidationError("Name is required.")

            # --- Mobile Phone: exactly 11 digits, starts with 010/011/012/015 ---
            if rec.mobile_phone:
                if not re.fullmatch(r'01[0125]\d{8}', rec.mobile_phone):
                    raise ValidationError(
                        "Mobile number must be 11 digits and start with 010, 011, 012, or 015."
                    )
            else:
                raise ValidationError("Mobile phone is required.")

            # --- Work Phone: at least 10 digits, start with 0 ---
            if rec.work_phone:
                if not re.fullmatch(r'0\d{9,}', rec.work_phone):
                    raise ValidationError(
                        "Work phone must start with 0 and contain at least 10 digits."
                    )
            else:
                raise ValidationError("Work phone is required.")

            # --- Address: at least 2 characters ---
            if rec.address:
                if len(rec.address.strip()) < 2:
                    raise ValidationError("Address must be at least 2 characters long.")
            else:
                raise ValidationError("Address is required.")

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        args = list(args or [])
        code_args = args + [
            '|', '|',
            ('mobile_phone', '=ilike', name),
            ('work_phone', '=ilike', name),
            ('code', '=ilike', name),
        ]

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
