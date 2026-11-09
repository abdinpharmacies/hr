# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AbAccountingJeHeader(models.Model):
    _name = 'ab_accounting_je_header'
    _inherit = 'ab_accounting_je_header'

    custody_header_ids = fields.One2many(
        'ab_custody_reconciliation_header',
        'je_header_id',
    )

    @api.constrains('custody_header_ids', 'costcenter_id')
    def _constrains_custody_accounting(self):
        for rec in self:
            costcenters = rec.custody_header_ids.employee_id.costcenter_id
            if len(costcenters) > 1:
                raise ValidationError(_("Many Costcenters!!!"))
            if costcenters and costcenters != rec.costcenter_id:
                raise ValidationError(_("Custody Costcenter must be same as JE Header Costcenter!"))
