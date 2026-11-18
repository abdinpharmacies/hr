import datetime
import logging

import re

import json
from lxml import etree
from odoo import models, fields, api, _, Command
from odoo.tools import SQL
from odoo.tools.float_utils import float_compare, float_is_zero
from odoo.exceptions import ValidationError, UserError


_logger = logging.getLogger(__name__)


class AbdinInventory(models.Model):
    _name = 'ab_fixed_asset_assets_inventory'
    _description = 'Assets Final Level'
    _rec_name = 'final_level'
    _order = 'id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'abdin_telegram']

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        result = super().get_view(view_id, view_type, **options)
        if view_type == 'form' and not self.env['ab_accounting_je_line'].has_access('read'):
            # Filter this response after the shared view cache. Existing record
            # permissions still govern journal access and asset operations.
            arch = etree.fromstring(result['arch'])
            for node in arch.xpath("//field[@name='je_line_ids'] | //label[@for='je_line_ids']"):
                node.getparent().remove(node)
            result['arch'] = etree.tostring(arch, encoding='unicode')
        return result

    je_header_id = fields.Many2one('ab_accounting_je_header')
    je_line_id = fields.Many2one('ab_accounting_je_line', required=False, ondelete='restrict')
    description = fields.Text()
    je_line_ids = fields.One2many('ab_accounting_je_line', 'fixed_asset_id')
    final_level = fields.Many2one('ab_fixed_asset_final_level', string="Asset", tracking=True,
                                  required=True)  # name of asset
    first_level = fields.Many2one(related='final_level.first_level', string="First Level")  # name of asset
    second_level = fields.Many2one(related='final_level.second_level', string="Second Level")  # name of asset
    asset_value = fields.Float(tracking=True, string='Old Value')

    asset_type = fields.Selection(
        selection=[
            ('regular', 'Regular'),
            ('inventory', 'Inventory'),
        ], default='regular'
    )
    scrapping_value = fields.Float()
    asset_source = fields.Selection(
        selection=[
            ('custody', 'Custody'),
            ('cash', 'Cash'),
            ('bank', 'Bank'),
            ('opening_balance', 'Opening Balance'),
        ],
    )

    asset_has_accounting_value = fields.Boolean(
        compute='_compute_asset_has_accounting_value',
        compute_sudo=True,
        search='_search_asset_has_accounting_value'
    )

    je_count = fields.Integer(
        compute='_compute_je_count',
        compute_sudo=True,
        search='_search_je_count'
    )

    last_depreciation_date = fields.Date(
        compute='_compute_last_depreciation_date',
        compute_sudo=True,
        search='_search_last_depreciation_date'
    )
    # Asset Cmputation From JEs
    asset_total_value = fields.Float(compute='_compute_asset_total_value', compute_sudo=True, string='Total Value')
    total_depr = fields.Float(compute='_compute_total_depr', compute_sudo=True, string='Total Depreciation')
    current_value_after_depr = fields.Float(compute='_compute_current_value_after_depr',
                                            compute_sudo=True,
                                            string='Value After Depreciation')

    current_store_id = fields.Many2one('ab_store', tracking=True,
                                       required=True,
                                       store=True, readonly=False)
    useful_life = fields.Integer(tracking=True, )
    depreciation_rate = fields.Float(compute="_get_depreciation_rate", store=True)
    asset_status = fields.Selection(
        [('active', 'Active'),
         ('new', 'New'),
         ('scrapped', 'Scrapped'),
         ('disposed', 'Disposed'),
         ('unknown', 'Unknown')],
        compute='_compute_asset_status', compute_sudo=True,
        search='_search_asset_status'
    )
    sales_value = fields.Float()
    inventory_standards_ids = fields.One2many(
        comodel_name='ab_fixed_asset_inventory_standards',
        inverse_name='asset_id',
        string='Asset Standards',
        required=False, copy=True)
    image = fields.Binary(string="Image", attachment=True, )
    quantity = fields.Integer(default=1, required=True)
    manual_value = fields.Float(compute='_compute_total_asset_value',
                                string="Manual Value",
                                store=True,
                                readonly=False)

    purchase_date = fields.Date()

    costcenter_id = fields.Many2one('ab_costcenter')
    old_id_to_move_img = fields.Integer(index=True)
    is_company_ownership = fields.Boolean(default=True)
    inventory_line_ids = fields.One2many('ab_fixed_asset_inventory_line', 'fixed_asset_header_id',
                                         string='Inventory Lines')

    active = fields.Boolean(default=True)

    @api.depends('asset_total_value', 'total_depr', 'useful_life', 'asset_has_accounting_value', 'scrapping_value')
    def _compute_asset_status(self):
        for rec in self:
            if not rec.asset_has_accounting_value:
                rec.asset_status = 'new'
            elif rec.useful_life == 0 and rec.scrapping_value > 0:
                rec.asset_status = 'scrapped'
            elif float_compare(rec.current_value_after_depr, 0, precision_digits=2) <= 0:
                rec.asset_status = 'disposed'
            elif rec.useful_life > 0:
                rec.asset_status = 'active'
            else:
                rec.asset_status = 'unknown'

    def _search_asset_status(self, operator, value):
        if operator not in ('=', '!=', 'in', 'not in'):
            raise UserError(_('Operation not supported for asset_status'))
        values = value if operator in ('in', 'not in') else [value]
        matches = self.search([]).filtered(lambda asset: asset.asset_status in values)
        return [('id', 'not in' if operator in ('!=', 'not in') else 'in', matches.ids)]

    def _compute_je_count(self):
        for rec in self:
            rec.je_count = self.env['ab_accounting_je_line'].sudo().search_count([('fixed_asset_id', '=', rec.id)])

    def _search_je_count(self, operator, val):
        one2many_field = 'je_line_ids'

        field = self._fields[one2many_field]
        # Get the relation model
        relation_model_name = field.comodel_name  # The related model name
        inverse_name = field.inverse_name
        relation_model = self.env[relation_model_name]  # Access the related model
        # Get the table name of the relation model
        relation_table_name = relation_model._table
        has_active = 'active' in relation_model._fields
        current_model = self._table
        available_operator = {'=', '!=', '>', '>=', '<', '<='}
        if operator not in available_operator:
            raise UserError(_('Operation not supported'))

        if not isinstance(val, int):
            raise UserError(_('Integer value only supported!'))

        if val == 0 and operator in ('=', '!='):
            ids = self.search([(one2many_field, operator, False)]).ids
        else:
            sql = f"""select org.id from {current_model} org
                        join {relation_table_name} rel on org.id=rel.{inverse_name}
                        {"where rel.active=true" if has_active else ""}
                        group by org.id
                        having count(*) {operator} {val}"""
            self.env.cr.execute(sql)
            ids = [row[0] for row in self.env.cr.fetchall()]
        return [('id', 'in', ids)]

    def _asset_cost_accounts(self):
        accounts = self.env['ab_accounting_account_guide'].with_context(active_test=False).search([
            ('internal_type', '=', 'fixed_asset'),
        ])
        return accounts | self.env.ref('ab_accounting.ab_accounting_account_guide_fixed_asset_inventory')

    def _posted_asset_lines(self, accounts):
        return self.env['ab_accounting_je_line'].sudo().search([
            ('fixed_asset_id', 'in', self.ids), ('account_id', 'in', accounts.ids),
            ('header_id.is_posted', '=', True), ('active', '=', True),
        ], order='due_date, id')

    @api.depends('je_line_ids.account_id', 'je_line_ids.due_date', 'je_line_ids.active', 'je_line_ids.header_id.is_posted')
    def _compute_last_depreciation_date(self):
        account = self.env.ref('ab_accounting.ab_accounting_account_guide_depreciation')
        dates = {}
        for line in self._posted_asset_lines(account):
            if line.due_date:
                dates[line.fixed_asset_id.id] = max(dates.get(line.fixed_asset_id.id, line.due_date), line.due_date)
        for rec in self:
            rec.last_depreciation_date = dates.get(rec.id, False)

    @api.depends('je_line_ids.account_id', 'je_line_ids.active', 'je_line_ids.header_id.is_posted')
    def _compute_asset_has_accounting_value(self):
        ids = set(self._posted_asset_lines(self._asset_cost_accounts()).fixed_asset_id.ids)
        for rec in self:
            rec.asset_has_accounting_value = rec.id in ids

    def _search_asset_has_accounting_value(self, operator, val):
        if operator not in ('=', '!=', 'in', 'not in'):
            raise UserError(_('Operation not supported'))
        values = val if operator in ('in', 'not in') else [val]
        matches = self.search([]).filtered(lambda asset: asset.asset_has_accounting_value in values)
        return [('id', 'not in' if operator in ('!=', 'not in') else 'in', matches.ids)]

    def _search_last_depreciation_date(self, operator, val):
        if operator not in ('=', '!=', 'in', 'not in', '>', '>=', '<', '<='):
            raise UserError(_('Operation not supported'))
        values = val if operator in ('in', 'not in') else [val]
        values = [fields.Date.to_date(value) if value else False for value in values]
        def matches(asset):
            date = asset.last_depreciation_date
            if operator in ('=', 'in'):
                return date in values
            if operator in ('!=', 'not in'):
                return date not in values
            if not date or not values[0]:
                return False
            return {'>': date > values[0], '>=': date >= values[0],
                    '<': date < values[0], '<=': date <= values[0]}[operator]
        return [('id', 'in', self.search([]).filtered(matches).ids)]

    @api.depends('je_line_ids.account_id', 'je_line_ids.debit_val', 'je_line_ids.credit_val',
                 'je_line_ids.active', 'je_line_ids.header_id.is_posted')
    def _compute_total_depr(self):
        # Remaining accumulated depreciation, not lifetime expense. Disposal and
        # direct cost write-downs must not be subtracted a second time.
        account = self.env.ref('ab_accounting.ab_accounting_account_guide_accumulated_depreciation')
        totals = {}
        for line in self._posted_asset_lines(account):
            key = line.fixed_asset_id.id
            totals[key] = totals.get(key, 0) + line.credit_val - line.debit_val
        for rec in self:
            rec.total_depr = totals.get(rec.id, 0)

    @api.depends('asset_total_value', 'total_depr')
    def _compute_current_value_after_depr(self):
        for rec in self:
            rec.current_value_after_depr = rec.asset_total_value - rec.total_depr

    @api.depends('je_line_ids.account_id', 'je_line_ids.debit_val', 'je_line_ids.credit_val',
                 'je_line_ids.active', 'je_line_ids.header_id.is_posted')
    def _compute_asset_total_value(self):
        totals = {}
        for line in self._posted_asset_lines(self._asset_cost_accounts()):
            key = line.fixed_asset_id.id
            totals[key] = totals.get(key, 0) + line.debit_val - line.credit_val
        for rec in self:
            rec.asset_total_value = totals.get(rec.id, 0)

    @api.depends('useful_life')
    def _get_depreciation_rate(self):
        for rec in self:
            rec.depreciation_rate = 100 / rec.useful_life if rec.useful_life else 0

    @api.depends('asset_value', 'quantity')
    def _compute_total_asset_value(self):
        for rec in self:
            if rec.asset_value and rec.quantity:
                rec.manual_value = rec.asset_value * rec.quantity

    @api.constrains('manual_value', 'useful_life', 'active')
    def assets_inventory_constrains(self):
        for rec in self:
            if rec.useful_life < 0:
                raise ValidationError(_('Useful life can not be negative!'))
            if not rec.manual_value > 0:
                raise ValidationError(_('Manual Value must be more than zero!'))
            if (not rec.active) and rec.je_line_ids:
                raise ValidationError(_("Can not archive asset that has JEs.\n"
                                        "Move JEs first to another asset, then archive."))
            if (not rec.je_line_ids) and (not rec.useful_life):
                raise ValidationError(_('Useful life must be more than zero for new Assets!'))
            # if rec.quantity > 1 and rec.asset_value > 1000:
            #     raise ValidationError(_('You can not enter a quantity more than (1) if its value more than 1000 LE!'))

    def write(self, vals):
        allowed_fields = {'message_ids', 'message_follower_ids', 'activity_ids', 'inventory_line_ids'}
        for rec in self:
            je_lines = self.env['ab_accounting_je_line'].sudo().search([
                ('fixed_asset_id', '=', rec.id)
            ], limit=1)
            if not rec.env.su and je_lines:
                disallowed = set(vals) - allowed_fields
                if disallowed:
                    raise UserError("This record is read-only. Only (Chatter, Inventory Lines) are allowed.")

        res = super().write(vals)
        return res

    @api.onchange('final_level')
    def onchange_final_level(self):
        # self === new asset created
        self.set_standards_for_asset(self)

    def set_standards_for_asset(self, asset):
        asset.update({'inventory_standards_ids': [Command.clear()] + [
            Command.create({'standard_id': standard.id})
            for standard in asset.final_level.standards_ids
        ]})

    def name_get(self):
        res = []
        for rec in self:
            res.append((rec.id, f"{rec.id} - {rec.final_level.name} - {rec.current_store_id.name}"))
        return res

    @api.depends('current_store_id', 'final_level')
    def _compute_display_name(self):
        """Keep the existing label format on the Odoo 19 display-name API."""
        names = dict(self.name_get())
        for record in self:
            record.display_name = names.get(record.id, False)

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        args = list(args or [])
        code_args = args + [('id', '=ilike', name), ]
        asset_store = name.split('-')

        ids = (self.with_user(name_get_uid) if name_get_uid else self).search(code_args, limit=limit).ids
        if not ids:
            if len(asset_store) > 1:
                args += [
                    ('final_level', 'ilike', asset_store[0].strip()),
                    ('current_store_id', 'ilike', asset_store[1].strip())
                ]
            else:
                args += [('final_level', operator, name), ]

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

    def _lock_workflow_rows(self, records):
        """A row version forces stale repeatable-read transactions to retry."""
        if not records:
            return
        records.flush_recordset()
        records.env.cr.execute(SQL(
            "SELECT id FROM %s WHERE id IN %s ORDER BY id FOR UPDATE",
            SQL.identifier(records._table), tuple(records.ids)))
        records.env.cr.execute(SQL(
            "UPDATE %s SET write_date = write_date WHERE id IN %s",
            SQL.identifier(records._table), tuple(records.ids)))
        records.invalidate_recordset()


    def _asset_account(self, suffix):
        account = self.env.ref('ab_accounting.ab_accounting_account_guide_' + suffix)
        if not account.active or not account.is_final:
            raise UserError(_('Configure an active posting account for %(account)s.', account=account.name))
        return account

    def _post_asset_journal(self, amounts, explanation):
        self.ensure_one()
        lines = []
        for asset, account, debit, credit in amounts:
            if float_is_zero(debit, precision_digits=2) and float_is_zero(credit, precision_digits=2):
                continue
            if not account.active or not account.is_final:
                raise UserError(_('Configure an active posting account for %(account)s.', account=account.name))
            lines.append(Command.create({
                'fixed_asset_id': asset.id, 'account_id': account.id,
                'store_id': asset.current_store_id.id, 'debit_val': round(debit, 2),
                'credit_val': round(credit, 2), 'due_date': fields.Date.today(),
                'explain': explanation,
            }))
        if not lines:
            raise UserError(_('There is no amount to post.'))
        # The validated asset workflow owns these exact journal values.
        # Preserve the acting user while bypassing unrelated manual-entry ACLs.
        header = self.env['ab_accounting_je_header'].sudo().create({
            'account_id': amounts[0][1].id,
            'doctype_id': self.env.ref('ab_accounting.ab_accounting_doctype_auto_je').id,
            'is_posted': True, 'line_ids': lines,
        })
        header.sudo_confirm_all_je()
        self.invalidate_recordset()
        return header

    def btn_depreciate(self, remove=False):
        if remove:
            raise UserError(_('Use an asset movement to scrap or dispose of an asset.'))
        with self.env.cr.savepoint():
            self._lock_workflow_rows(self)
            for asset in self.sorted('id'):
                asset._depreciate_asset()
        return True

    def _depreciate_asset(self, allow_reversal=False):
        self.ensure_one()
        costs = self._posted_asset_lines(self._asset_cost_accounts())
        acquisitions = costs.filtered(lambda line: line.debit_val > 0)
        if not acquisitions or self.asset_total_value <= 0:
            raise ValidationError(_('A posted acquisition with a positive cost is required.'))
        today = fields.Date.today()
        if any(not line.due_date or line.due_date > today for line in acquisitions):
            raise ValidationError(_('Acquisition dates must be set and cannot be in the future.'))
        if self.useful_life <= 0:
            raise ValidationError(_('Useful life must be positive for depreciation.'))
        cost = self.asset_total_value
        previous = self.total_depr
        if previous < 0 or float_compare(previous, cost, precision_digits=2) > 0:
            raise ValidationError(_('Review the asset cost and accumulated depreciation before posting.'))
        days = (today - acquisitions[0].due_date).days
        target = round(min(cost, cost * days / (self.useful_life * 365)), 2)
        delta = round(target - previous, 2)
        # Regular depreciation never reverses a previous write-down. Revaluation
        # after an explicitly approved useful-life change is a separate action.
        if float_is_zero(delta, precision_digits=2) and allow_reversal:
            return self.env['ab_accounting_je_header']
        if float_is_zero(delta, precision_digits=2) or (delta < 0 and not allow_reversal):
            raise UserError(_('No additional depreciation is due for this asset.'))
        expense = self._asset_account('depreciation')
        accumulated = self._asset_account('accumulated_depreciation')
        return self._post_asset_journal([
            (self, expense, max(delta, 0), max(-delta, 0)),
            (self, accumulated, max(-delta, 0), max(delta, 0)),
        ], _('Depreciation for %(days)s days', days=days))

    def _dispose_asset(self):
        self.ensure_one()
        costs = self._posted_asset_lines(self._asset_cost_accounts())
        balances = {}
        for line in costs:
            balances[line.account_id] = balances.get(line.account_id, 0) + line.debit_val - line.credit_val
        cost = self.asset_total_value
        accumulated = self.total_depr
        if cost <= 0 or accumulated < 0 or float_compare(accumulated, cost, precision_digits=2) > 0:
            raise ValidationError(_('Review the asset cost and accumulated depreciation before posting.'))
        if any(value < 0 for value in balances.values()):
            raise ValidationError(_('Review the asset cost and accumulated depreciation before posting.'))
        amounts = [(self, account, 0, value) for account, value in balances.items()]
        amounts += [(self, self._asset_account('accumulated_depreciation'), accumulated, 0),
                    (self, self._asset_account('depreciation'), cost - accumulated, 0)]
        return self._post_asset_journal(amounts, _('Asset disposal'))

    def action_asset_movement(self):
        return {
            'type': 'ir.actions.act_window', 'name': _('Asset Movement'),
            'res_model': 'ab_fixed_asset_move_wizard', 'view_mode': 'form',
            'target': 'current', 'context': {'default_src_fixed_asset_ids': self.ids},
        }

    @api.model
    def _send_asset_notification(self, msg, after, attachment=None):
        # Notifications are optional; malformed credentials or chat IDs must not
        # roll back asset creation or a successfully validated movement.
        try:
            return self.send_by_bot(
                self.get_chat_id('telegram_fixed_asset_move_group_chat_id'),
                msg=msg, after=after, attachment=attachment,
            )
        except (ValueError, TypeError) as error:
            # Do not log exception arguments: configuration can contain secrets.
            _logger.warning(
                'Fixed asset Telegram notification skipped: invalid bot or chat configuration (%s).',
                type(error).__name__,
            )
            return False

    @api.model_create_multi
    def create(self, vals_list):
        records = self.browse()
        for values in vals_list:
            records |= self._create_one_ab_fixed_asset_abdininventory(values)
        return records

    def _create_one_ab_fixed_asset_abdininventory(self, values):
        res = super().create(values)

        msg = f"""<div>New Asset Created</div>
        <div>Asset ID: {res.id}</div>
        <div>Asset name: {res.display_name} </div>
        """

        after = "\n\nBy %s" % (self.env.user.name,)
        self._send_asset_notification(msg, after)
        return res
