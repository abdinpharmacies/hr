# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class Supplier(models.Model):
    _name = 'ab_supplier'
    _description = 'ab_supplier'

    _parent_store = True
    _parent_name = "parent_id"  # optional if field is 'parent_id'
    parent_path = fields.Char(index=True)

    parent_id = fields.Many2one('ab_supplier',
                                string='Parent Supplier',
                                ondelete='restrict',
                                index=True)

    child_ids = fields.One2many(
        'ab_supplier', 'parent_id',
        string='Sub Suppliers')
    name = fields.Char()
    costcenter_id = fields.Many2one('ab_costcenter', index=True)
    code = fields.Char(required=True, index=True)
    telephone = fields.Char()
    address = fields.Char()
    registration_number = fields.Char()
    end_date = fields.Date()
    max_credit = fields.Float()
    current_credit = fields.Float()
    return_interval = fields.Integer()
    tax_type = fields.Selection([('through_supplier', 'Through Supplier'),
                                 ('tax_payment', 'Tax Payment'),
                                 ('non_tax_payment', 'Non-tax Payment')])
    section = fields.Selection([('medical', 'Medical'), ('imp_med', 'Imported Med'),
                                ('cosmo', 'Cosmetics'), ('imp_cosmo', 'Imported Cosmetics'),
                                ('other', 'Other')])
    territory = fields.Selection([('upper_egypt', 'Upper Egypt'),
                                  ('lower_egypt', 'Lower Egypt'),
                                  ('both', 'Both'),
                                  ], default='both')

    purchase_limit = fields.Float()
    active = fields.Boolean(default=True)
    description = fields.Text()

    def _get_bracket_domain(self):
        """Keep the bracket storage relationship inside the supplier module."""
        self.check_access('read')
        return fields.Domain('supplier_id', 'in', self.mapped('costcenter_id').ids)

    def _has_bracket(self, bracket):
        """Validate ownership without exposing cost-center details to callers."""
        self.ensure_one()
        self.check_access('read')
        bracket.check_access('read')
        return bool(bracket and self.costcenter_id and bracket.supplier_id == self.costcenter_id)

    @api.model
    def _resolve_legacy_supplier_reference(self, reference_id):
        """Resolve old cost-center references during migration only.

        Return the supplier and original model name for the caller's audit log.
        Existing suppliers are never renamed, reclassified, or silently remapped.
        """
        source = self.env['ab_costcenter'].with_context(active_test=False).browse(reference_id).exists()
        if not source or not source.name or not source.code:
            raise ValidationError('Legacy supplier reference %s has an incomplete source cost center.' % reference_id)
        Supplier = self.with_context(active_test=False)
        supplier = Supplier.search(fields.Domain('costcenter_id', '=', source.id))
        if len(supplier) > 1:
            raise ValidationError('Cost center %s has multiple linked suppliers.' % source.id)
        if not supplier:
            duplicate = Supplier.search(
                fields.Domain('code', '=', source.code) | fields.Domain('name', '=ilike', source.name))
            if duplicate:
                raise ValidationError('Cost center %s has unlinked supplier name/code matches; review them first.' % source.id)
            supplier = Supplier.create({
                'name': source.name, 'code': source.code, 'costcenter_id': source.id,
                'active': source.active,
                'telephone': source.tel_no or source.mobile_phone or False,
                'description': 'Created during legacy supplier-claim recovery from cost center %s. '
                               'Payment/business defaults require review before new claim submission.' % source.id,
            })
        return supplier, source._name

    @api.model
    def _search_display_name(self, operator, value):
        code_ids = self._search([('code', '=ilike', value)])
        if code_ids:
            return [('id', 'in', code_ids)]
        return [('name', operator, value)]
