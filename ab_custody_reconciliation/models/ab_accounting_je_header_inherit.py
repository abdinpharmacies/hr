# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from lxml import etree


class AbAccountingJeHeader(models.Model):
    _name = 'ab_accounting_je_header'
    _inherit = 'ab_accounting_je_header'

    custody_header_ids = fields.One2many(
        'ab_custody_reconciliation_header',
        'je_header_id',
    )

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        result = super().get_view(view_id, view_type, **options)
        if view_type == 'form' and not self.env['ab_custody_reconciliation_header'].has_access('read'):
            # Prune after the shared view cache: visibility follows this user's
            # existing ACLs without changing field or record permissions.
            arch = etree.fromstring(result['arch'])
            for node in arch.xpath("//field[@name='custody_header_ids'] | //label[@for='custody_header_ids']"):
                node.getparent().remove(node)
            result['arch'] = etree.tostring(arch, encoding='unicode')
        return result

    @api.constrains('custody_header_ids', 'costcenter_id')
    def _constrains_custody_accounting(self):
        for rec in self:
            costcenters = rec.custody_header_ids.employee_id.costcenter_id
            if len(costcenters) > 1:
                raise ValidationError(_("Many Costcenters!!!"))
            if costcenters and costcenters != rec.costcenter_id:
                raise ValidationError(_("Custody Costcenter must be same as JE Header Costcenter!"))
