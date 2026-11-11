import math

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


ACCOUNT_FIELDS = {
    'drawer_account_id': 'asset', 'treasury_account_id': 'asset',
    'transit_account_id': 'asset', 'card_account_id': 'asset',
    'wallet_account_id': 'asset', 'other_account_id': 'asset',
    'sales_account_id': 'income', 'sales_return_account_id': 'income',
    'inventory_account_id': 'asset', 'cost_account_id': 'expense',
    'tax_account_id': 'liability', 'difference_account_id': None,
    'shortage_account_id': 'expense', 'surplus_account_id': 'income',
}


class BranchCashConfiguration(models.Model):
    _name = 'ab_accounting_cash_config'
    _description = 'Branch Cash Accounting Configuration'
    _rec_name = 'store_id'

    store_id = fields.Many2one('ab_store', required=True, ondelete='restrict')
    branch_code = fields.Char(related='store_id.code', string='Branch Code')
    replica_db_id = fields.Many2one('ab_replica_db', string='Branch Database', ondelete='restrict')
    db_serial = fields.Integer(related='replica_db_id.db_serial', string='Database Serial')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    active = fields.Boolean(default=True)
    enabled = fields.Boolean(string='Enable Automatic Cash Accounting', default=False)
    posting_user_id = fields.Many2one('res.users', required=True, default=lambda self: self.env.user, ondelete='restrict')
    doctype_id = fields.Many2one('ab_accounting_doctype', string='Cash Document Type', ondelete='restrict')
    drawer_account_id = fields.Many2one('ab_accounting_account_guide', string='Drawer Account', ondelete='restrict')
    treasury_account_id = fields.Many2one('ab_accounting_account_guide', string='Treasury Account', ondelete='restrict')
    transit_account_id = fields.Many2one('ab_accounting_account_guide', string='Cash in Transit Account', ondelete='restrict')
    card_account_id = fields.Many2one('ab_accounting_account_guide', string='Card Clearing Account', ondelete='restrict')
    wallet_account_id = fields.Many2one('ab_accounting_account_guide', string='Wallet Clearing Account', ondelete='restrict')
    other_account_id = fields.Many2one('ab_accounting_account_guide', string='Other Payments Account', ondelete='restrict')
    sales_account_id = fields.Many2one('ab_accounting_account_guide', string='Sales Account', ondelete='restrict')
    sales_return_account_id = fields.Many2one('ab_accounting_account_guide', string='Sales Returns Account', ondelete='restrict')
    inventory_account_id = fields.Many2one('ab_accounting_account_guide', string='Inventory Account', ondelete='restrict')
    cost_account_id = fields.Many2one('ab_accounting_account_guide', string='Cost of Sales Account', ondelete='restrict')
    tax_account_id = fields.Many2one('ab_accounting_account_guide', string='Sales Tax Account', ondelete='restrict')
    difference_account_id = fields.Many2one('ab_accounting_account_guide', string='Pending Cash Differences Account', ondelete='restrict')
    shortage_account_id = fields.Many2one('ab_accounting_account_guide', string='Approved Cash Shortages Account', ondelete='restrict')
    surplus_account_id = fields.Many2one('ab_accounting_account_guide', string='Approved Cash Surpluses Account', ondelete='restrict')
    drawer_balance = fields.Monetary(compute='_compute_balances', string='Posted Drawer Balance')
    treasury_balance = fields.Monetary(compute='_compute_balances', string='Posted Treasury Balance')
    transit_balance = fields.Monetary(compute='_compute_balances', string='Posted Cash in Transit')
    _branch_unique = models.Constraint('UNIQUE(store_id, company_id)', 'A branch has one cash accounting configuration per company.')

    def _compute_balances(self):
        roles = {'drawer_balance': 'drawer_account_id', 'treasury_balance': 'treasury_account_id',
                 'transit_balance': 'transit_account_id'}
        accounts = self.drawer_account_id | self.treasury_account_id | self.transit_account_id
        domain = (fields.Domain('store_id', 'in', self.store_id.ids)
                  & fields.Domain('account_id', 'in', accounts.ids)
                  & fields.Domain('header_id.is_posted', '=', True))
        totals = {(store.id, account.id): total for store, account, total in
                  self.env['ab_accounting_je_line']._read_group(domain, ['store_id', 'account_id'], ['net_val:sum'])}
        for config in self:
            for field, role in roles.items():
                config[field] = totals.get((config.store_id.id, config[role].id), 0)

    def _check_manager(self):
        if not (self.env.is_system() or self.env.user.has_group('ab_accounting.group_ab_accounting_manager')):
            raise AccessError(_('Accounting manager access is required to configure branch cash accounts.'))

    @api.model_create_multi
    def create(self, vals_list):
        self._check_manager()
        return super().create(vals_list)

    def write(self, vals):
        self._check_manager()
        self.check_access('write')
        self.lock_for_update()
        if set(vals) & (set(ACCOUNT_FIELDS) | {'store_id', 'replica_db_id', 'company_id', 'enabled', 'active', 'posting_user_id', 'doctype_id'}):
            if self.env['ab_accounting_cash_entry'].sudo().search_count([('config_id', 'in', self.ids)], limit=1):
                raise ValidationError(_('Cash accounting configuration with posted history cannot be changed.'))
        return super().write(vals)

    def unlink(self):
        raise AccessError(_('Archive unused cash accounting configuration instead of deleting it.'))

    @api.constrains('enabled', 'active', 'store_id', 'replica_db_id', 'company_id', 'posting_user_id', 'doctype_id', *ACCOUNT_FIELDS)
    def _validate_configuration(self):
        for config in self:
            if config.company_id not in self.env.companies:
                raise AccessError(_('Cash accounting must belong to an allowed company.'))
            if 'company_id' in config.store_id._fields and config.store_id.company_id != config.company_id:
                raise ValidationError(_('The cash accounting company must match the branch company.'))
            if config.replica_db_id.allowed_sales_store_ids and config.store_id not in config.replica_db_id.allowed_sales_store_ids:
                raise ValidationError(_('The branch must belong to the selected database.'))
            if not config.enabled:
                continue
            if not config.active or not config.store_id.active or not config.doctype_id:
                raise ValidationError(_('Choose an active branch and a cash document type before enabling accounting.'))
            if config.currency_id.decimal_places != 2:
                raise ValidationError(_('Cash accounting requires a currency with two decimal places.'))
            user = config.posting_user_id
            if not user.active or config.company_id not in user.company_ids or not user.has_group('ab_accounting.group_ab_accounting_accountant'):
                raise ValidationError(_('The posting user must be an active accountant in the configured company.'))
            if user.id != 1 and (config.doctype_id not in user.doctype_ids or config.store_id in user.store_ids):
                raise ValidationError(_('The posting user must be authorized for this branch and document type.'))
            accounts = []
            for name, group in ACCOUNT_FIELDS.items():
                account = config[name]
                if not account or not account.active or not account.is_final or not account.has_store:
                    raise ValidationError(_('Configure active final accounts with branch balances for every cash accounting role.'))
                if group and account.internal_group != group:
                    raise ValidationError(_('The account type does not match its cash accounting role.'))
                if account.has_costcenter or account.has_due_date:
                    raise ValidationError(_('Cash accounting accounts must not require cost centers or due dates.'))
                account.with_user(user)._validate_posting_account(own=True)
                accounts.append(account.id)
            if len(accounts) != len(set(accounts)):
                raise ValidationError(_('Use separate accounts for drawer, treasury, clearing, revenue, cost, tax and differences.'))

    @api.model
    def _for_store(self, store, company):
        config = self.sudo().search([('store_id', '=', store.id), ('company_id', '=', company.id), ('enabled', '=', True)], limit=1)
        return config

    def _post(self, operation_key, source, reference, amounts, accounting_date=None):
        self.ensure_one()
        self.lock_for_update()
        self.invalidate_recordset()
        self._validate_configuration()
        if not self.enabled or not self.active:
            raise ValidationError(_('Enable cash accounting before posting.'))
        currency = self.currency_id
        lines = []
        for role, value in amounts.items():
            if role not in ACCOUNT_FIELDS or not math.isfinite(value):
                raise ValidationError(_('Invalid cash accounting amount or account role.'))
            value = currency.round(value)
            if currency.is_zero(value):
                continue
            lines.append({'account_id': self[role].id, 'store_id': self.store_id.id,
                'doc_no': operation_key, 'explain': reference,
                'debit_val': max(value, 0), 'credit_val': max(-value, 0)})
        if currency.compare_amounts(sum(line['debit_val'] for line in lines), sum(line['credit_val'] for line in lines)):
            raise ValidationError(_('The cash accounting entry must balance.'))
        Entry = self.env['ab_accounting_cash_entry'].sudo()
        existing = Entry.search([('operation_key', '=', operation_key)], limit=1)
        if existing:
            def economic_values(rows):
                return sorted((row['account_id'], row['store_id'], row['debit_val'], row['credit_val']) for row in rows)
            if existing.config_id != self or existing.source_model != source._name or existing.source_id != source.id or economic_values(existing.lines_snapshot) != economic_values(lines):
                raise ValidationError(_('This operation already has a different accounting entry.'))
            return existing
        if not lines:
            return Entry
        posting = self.env['ab_accounting_je_header'].with_user(self.posting_user_id).with_context(allowed_company_ids=[self.company_id.id])
        journal = posting.post_journal({'account_id': lines[0]['account_id'], 'store_id': self.store_id.id,
            'doctype_id': self.doctype_id.id, 'posted_date': accounting_date or fields.Date.context_today(self),
            'res_header_ref': source._name, 'res_header_id': source.id, 'lines': lines})
        return super(CashAccountingEntry, Entry).create({'config_id': self.id, 'operation_key': operation_key,
            'reference': reference, 'source_model': source._name, 'source_id': source.id,
            'journal_id': journal.id, 'lines_snapshot': lines})


class CashAccountingEntry(models.Model):
    _name = 'ab_accounting_cash_entry'
    _description = 'Branch Cash Accounting Entry'
    _rec_name = 'reference'
    _order = 'id desc'

    config_id = fields.Many2one('ab_accounting_cash_config', required=True, readonly=True, ondelete='restrict')
    store_id = fields.Many2one(related='config_id.store_id', store=True)
    company_id = fields.Many2one(related='config_id.company_id', store=True)
    operation_key = fields.Char(required=True, readonly=True, index=True)
    reference = fields.Char(required=True, readonly=True)
    source_model = fields.Char(required=True, readonly=True)
    source_id = fields.Integer(required=True, readonly=True)
    journal_id = fields.Many2one('ab_accounting_je_header', required=True, readonly=True, ondelete='restrict')
    lines_snapshot = fields.Json(readonly=True)
    _operation_unique = models.Constraint('UNIQUE(operation_key)', 'Each cash operation has one accounting entry.')

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError(_('Cash accounting entries are created by validated business operations.'))

    def write(self, vals):
        raise AccessError(_('Posted cash accounting links cannot be changed.'))

    def unlink(self):
        raise AccessError(_('Posted cash accounting links cannot be deleted.'))
