from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PurchaseAccountingConfig(models.Model):
    _name = 'ab_purchase_accounting_config'
    _description = 'Purchase Accounting Configuration'
    _order = 'company_id, branch_id, activation_date desc, id desc'
    _rec_name = 'display_name'

    display_name = fields.Char(compute='_compute_display_name')
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    branch_id = fields.Many2one(
        'ab_store',
        required=True,
        ondelete='restrict',
        index=True,
        domain="[('allow_purchase', '=', True), ('active', '=', True)]",
    )
    active = fields.Boolean(default=True)
    activation_date = fields.Date(
        required=True,
        default=lambda self: fields.Date.context_today(self),
        help='Only purchase documents dated on or after this date are posted automatically.',
    )
    posting_user_id = fields.Many2one(
        'res.users',
        required=True,
        default=lambda self: self.env.user,
        ondelete='restrict',
        string='Posting User',
        help='Dedicated accounting integration user used to call the Auto JE posting contract.',
    )
    purchase_doctype_id = fields.Many2one(
        'ab_accounting_doctype',
        required=True,
        ondelete='restrict',
        string='Purchase Receipt Document Type',
    )
    return_doctype_id = fields.Many2one(
        'ab_accounting_doctype',
        required=True,
        ondelete='restrict',
        string='Purchase Return Document Type',
    )
    inventory_account_id = fields.Many2one(
        'ab_accounting_account_guide',
        required=True,
        ondelete='restrict',
        string='Inventory Account',
    )
    tax_account_id = fields.Many2one(
        'ab_accounting_account_guide',
        ondelete='restrict',
        string='Purchase Tax Account',
    )
    supplier_account_id = fields.Many2one(
        'ab_accounting_account_guide',
        required=True,
        ondelete='restrict',
        string='Supplier Account',
    )
    default_costcenter_id = fields.Many2one(
        'ab_costcenter',
        ondelete='restrict',
        string='Default Cost Center',
        help='Used only when a configured account requires a cost center and the supplier has none.',
    )
    supplier_due_days = fields.Integer(
        default=0,
        string='Supplier Due Days',
        help='Used when a configured account requires due dates.',
    )
    receipt_account_ids = fields.One2many(
        'ab_purchase_accounting_receipt_account',
        'config_id',
        string='Non-purchase Receipt Offset Accounts',
    )
    note = fields.Text()

    _activation_unique = models.Constraint(
        'UNIQUE(company_id, branch_id, activation_date)',
        'Purchase accounting activation dates must be unique per company and branch.',
    )

    @api.depends('company_id', 'branch_id', 'activation_date')
    def _compute_display_name(self):
        for rec in self:
            company = rec.company_id.display_name or ''
            branch = rec.branch_id.display_name or ''
            date = rec.activation_date or ''
            rec.display_name = '%s / %s / %s' % (company, branch, date)

    @api.constrains(
        'company_id',
        'branch_id',
        'purchase_doctype_id',
        'return_doctype_id',
        'inventory_account_id',
        'tax_account_id',
        'supplier_account_id',
        'posting_user_id',
        'supplier_due_days',
        'default_costcenter_id',
    )
    def _check_configuration(self):
        for rec in self:
            if rec.supplier_due_days < 0:
                raise ValidationError(_('Supplier due days cannot be negative.'))
            if not rec.branch_id.active or not rec.branch_id.allow_purchase:
                raise ValidationError(_('Purchase accounting requires an active purchase branch.'))
            rec._check_company_records()
            rec._check_posting_user()

    def _check_mappings(self):
        self.ensure_one()
        supplier = self.supplier_account_id
        inventory = self.inventory_account_id
        tax = self.tax_account_id
        def under(account, xmlid):
            parent = self.env.ref(xmlid, raise_if_not_found=False)
            return bool(parent and account and parent.id in [int(i) for i in (account.parent_path or '').split('/') if i])
        if not supplier or supplier.internal_group != 'liability' or not (supplier.internal_type == 'payable' or under(supplier, 'ab_accounting.ab_accounting_account_guide_suppliers')):
            raise ValidationError(_('Configure a supplier payable account under the supplier account guide.'))
        if not inventory or inventory.internal_group != 'asset' or not under(inventory, 'ab_accounting.ab_accounting_account_guide_inventory'):
            raise ValidationError(_('Configure an inventory posting account under the inventory account guide.'))
        if tax and not under(tax, 'ab_accounting.ab_accounting_account_guide_taxes'):
            raise ValidationError(_('Configure a tax posting account under the tax account guide.'))
        accounts = [supplier.id, inventory.id] + ([tax.id] if tax else [])
        if len(accounts) != len(set(accounts)):
            raise ValidationError(_('Supplier, inventory and tax accounts must be distinct.'))
        for account in supplier | inventory | tax:
            account.with_user(self.posting_user_id)._validate_posting_account(own=account == supplier)
        if self.default_costcenter_id and not self.default_costcenter_id.active:
            raise ValidationError(_('Cost center must be active.'))

    def _check_company_records(self):
        self.ensure_one()
        self._check_mappings()
        for account in self.inventory_account_id | self.tax_account_id | self.supplier_account_id:
            if not account.active or not account.is_final or account.child_ids:
                raise ValidationError(_('Purchase accounting accounts must be active posting accounts.'))
        for doctype in self.purchase_doctype_id | self.return_doctype_id:
            if doctype not in self.posting_user_id.doctype_ids and self.posting_user_id.id != 1:
                raise ValidationError(_('The posting user must be authorized for both document types.'))
            if not getattr(doctype, 'active', True):
                raise ValidationError(_('Purchase accounting document types must be active.'))

    def _check_posting_user(self):
        self.ensure_one()
        user = self.posting_user_id
        if not user.active or self.company_id not in user.company_ids:
            raise ValidationError(_('The posting user must be allowed on the configured company.'))
        if not (
            user.has_group('ab_accounting.group_ab_accounting_accountant')
            or user.has_group('base.group_system')
        ):
            raise ValidationError(_('The posting user must have Accountant access.'))

    @api.model
    def _for_branch_date(self, company, branch, accounting_date):
        if not company or not branch or not accounting_date:
            raise ValidationError(_('Purchase accounting requires company, branch and accounting date.'))
        config = self.search(
            [
                ('active', '=', True),
                ('company_id', '=', company.id),
                ('branch_id', '=', branch.id),
                ('activation_date', '<=', accounting_date),
            ],
            order='activation_date desc, id desc',
            limit=1,
        )
        if not config:
            raise ValidationError(
                _('No active purchase accounting configuration exists for %(branch)s on %(date)s.')
                % {'branch': branch.display_name, 'date': accounting_date}
        )
        config._check_configuration()
        return config

    def _non_purchase_receipt_offset_account(self, receipt_type):
        self.ensure_one()
        if not receipt_type:
            raise ValidationError(_('Select a receipt type before posting non-purchase receipt accounting.'))
        mapping = self.receipt_account_ids.filtered(lambda rec: rec.receipt_type_id == receipt_type)
        if not mapping:
            raise ValidationError(
                _('No offset account is configured for non-purchase receipt type %(receipt_type)s.')
                % {'receipt_type': receipt_type.display_name}
            )
        mapping[:1]._check_offset_account()
        return mapping[:1].offset_account_id

    def _with_posting_user(self):
        self.ensure_one()
        return self.with_user(self.posting_user_id).with_context(
            allowed_company_ids=[self.company_id.id]
        )


class PurchaseAccountingReceiptAccount(models.Model):
    _name = 'ab_purchase_accounting_receipt_account'
    _description = 'Purchase Accounting Receipt Offset Account'
    _rec_name = 'receipt_type_id'

    config_id = fields.Many2one(
        'ab_purchase_accounting_config',
        required=True,
        ondelete='cascade',
    )
    company_id = fields.Many2one(related='config_id.company_id', store=True)
    receipt_type_id = fields.Many2one(
        'ab_purchase_ob_receipt_type',
        required=True,
        ondelete='restrict',
        string='Receipt Type',
    )
    offset_account_id = fields.Many2one(
        'ab_accounting_account_guide',
        required=True,
        ondelete='restrict',
        string='Offset Account',
    )

    _receipt_type_unique = models.Constraint(
        'UNIQUE(config_id, receipt_type_id)',
        'Configure each non-purchase receipt type only once per purchase accounting setup.',
    )

    @api.constrains('config_id', 'offset_account_id')
    def _check_offset_account(self):
        for rec in self:
            account = rec.offset_account_id
            account.with_user(rec.config_id.posting_user_id)._validate_posting_account(own=True)
            if not account.active or not account.is_final or account.child_ids:
                raise ValidationError(_('Receipt offset accounts must be active posting accounts.'))
