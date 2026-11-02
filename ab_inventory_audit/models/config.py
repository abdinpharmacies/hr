from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class AuditConfig(models.Model):
    _name = 'ab_inventory_audit_config'
    _description = 'Audit Accounting Configuration'
    _rec_name = 'store_id'

    store_id = fields.Many2one('ab_store', required=True, ondelete='restrict')
    company_id = fields.Many2one(related='store_id.company_id', store=True)
    date_from = fields.Date(required=True, default=fields.Date.today)
    date_to = fields.Date()
    inventory_account_id = fields.Many2one('ab_accounting_account_guide', required=True, ondelete='restrict')
    shortage_account_id = fields.Many2one('ab_accounting_account_guide', required=True, ondelete='restrict')
    surplus_account_id = fields.Many2one('ab_accounting_account_guide', required=True, ondelete='restrict')
    doctype_id = fields.Many2one('ab_accounting_doctype', required=True, ondelete='restrict')
    costcenter_id = fields.Many2one('ab_costcenter', ondelete='restrict')

    def _authorize(self):
        if not (self.env.user.has_group('base.group_system') or
                (self.env.user.has_group('ab_inventory_audit.group_config') and
                 self.env.user.has_group('ab_accounting.group_ab_accounting_accountant'))):
            raise AccessError(_('Accounting configuration requires financial administration permission.'))

    @api.model_create_multi
    def create(self, vals_list):
        self._authorize()
        with self.env.cr.savepoint():
            records = super().create(vals_list)
            records._validate_scope()
            return records

    def write(self, vals):
        self._authorize()
        self.check_access('write')
        self.lock_for_update()
        if self.env['ab_inventory_audit'].sudo().search_count([
                ('config_id', 'in', self.ids), ('state', '=', 'posted')], limit=1):
            raise ValidationError(_('Create a new configuration version for future audits.'))
        with self.env.cr.savepoint():
            result = super().write(vals)
            self._validate_scope()
            return result

    def unlink(self):
        raise AccessError(_('Accounting configuration history cannot be deleted.'))

    def _validate_scope(self):
        for rec in self:
            self.env['ab_inventory_audit']._check_branch(rec.store_id)
            if rec.date_to and rec.date_to < rec.date_from:
                raise ValidationError(_('The effective period is invalid.'))

    def _snapshot(self):
        self.ensure_one()
        return {name: self[name].id for name in ('inventory_account_id', 'shortage_account_id',
                                                'surplus_account_id', 'doctype_id', 'costcenter_id')} | {
            'date_from': str(self.date_from), 'date_to': str(self.date_to), 'store_id': self.store_id.id}

    def _validate_posting(self):
        self.ensure_one()
        self._validate_scope()
        today = fields.Date.context_today(self)
        if today < self.date_from or (self.date_to and today > self.date_to):
            raise ValidationError(_('The accounting configuration is outside its effective period.'))
        self.inventory_account_id._validate_posting_account(own=True)
        self.shortage_account_id._validate_posting_account()
        self.surplus_account_id._validate_posting_account()
        if not self.env.su and self.doctype_id not in self.env.user.doctype_ids:
            raise AccessError(_('You are not authorized for this document type.'))
        accounts = self.inventory_account_id | self.shortage_account_id | self.surplus_account_id
        for account in accounts:
            self.env['ab_accounting_je_line'].new({
                'account_id': account.id, 'store_id': self.store_id.id,
                'costcenter_id': self.costcenter_id.id, 'due_date': today,
                'explain': _('Inventory audit approval validation'), 'debit_val': 1,
            })._validate_posting_line()
