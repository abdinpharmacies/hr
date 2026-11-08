from odoo import fields, models, _
from odoo.exceptions import AccessError

from ..services.legacy_activation import LegacyCodeSecurity


class LegacyCustomer(models.Model):
    _name = 'ab_ecommerce_legacy_customer'
    _description = 'Legacy Customer'
    _order = 'id desc'

    name = fields.Char(required=True)
    source_key = fields.Char(required=True, index=True, readonly=True)
    phone = fields.Char(required=True, index=True, readonly=True)
    source_store = fields.Char(readonly=True, groups='base.group_system')
    batch_id = fields.Many2one('ab_ecommerce_legacy_batch', required=True, readonly=True, ondelete='restrict')
    website_id = fields.Many2one('website', required=True, readonly=True, ondelete='restrict')
    company_id = fields.Many2one(related='website_id.company_id', store=True, index=True)
    active = fields.Boolean(default=True)
    partner_id = fields.Many2one('res.partner', readonly=True, index=True, ondelete='restrict', groups='base.group_system')
    code_hash = fields.Char(readonly=True, groups='base.group_system')
    expires_at = fields.Datetime(readonly=True)
    attempts = fields.Integer(default=0, readonly=True, groups='base.group_system')
    claimed_at = fields.Datetime(readonly=True)
    claimed_user_id = fields.Many2one('res.users', readonly=True, ondelete='restrict', groups='base.group_system')
    _source_unique = models.Constraint('UNIQUE(website_id, source_key)', 'This source customer has already been imported.')
    _phone_unique = models.Constraint('UNIQUE(website_id, phone)', 'This phone is already assigned to a legacy customer.')
    _partner_unique = models.Constraint('UNIQUE(website_id, partner_id)', 'This account is already linked to a legacy customer.')

    def unlink(self):
        raise AccessError(_('Archive legacy customers instead of deleting them.'))

    def _code_digest(self, code):
        self.ensure_one()
        return LegacyCodeSecurity(self.env)._digest(f'legacy-code:{self.website_id.id}:{self.source_key}:{code}')
