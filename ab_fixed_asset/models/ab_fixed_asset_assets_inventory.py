import datetime

import re

import json
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class AbdinInventory(models.Model):
    _name = 'ab_fixed_asset_assets_inventory'
    _description = 'Assets Final Level'
    _rec_name = 'final_level'
    _order = 'id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'abdin_telegram']

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

    def _compute_asset_status(self):
        for rec in self:
            asset_total_value = rec.asset_total_value
            total_depr = rec.total_depr
            current_value_after_depr = rec.current_value_after_depr
            useful_life = rec.useful_life
            je_count = rec.je_count
            if je_count == 0:
                rec.asset_status = 'new'
            elif current_value_after_depr < 1 and rec.asset_has_accounting_value:
                rec.asset_status = 'disposed'
            elif current_value_after_depr > 1 and useful_life > 0:
                rec.asset_status = 'active'
            elif useful_life == 0 and total_depr > 0:
                rec.asset_status = 'scrapped'
            else:
                rec.asset_status = 'unknown'

    def _search_asset_status(self, operator, value):
        if operator not in ['=', '!=']:
            raise UserError(_('Operation not supported for asset_status'))

        if value == 'new':
            matched_ids = self.sudo().search([('je_count', '=', 0)]).ids
        else:
            fixed_asset_account = self.env['ab_accounting_account_guide'].search(
                [('internal_type', '=', 'fixed_asset')])
            depr_account = self.env.ref('ab_accounting.ab_accounting_account_guide_depreciation')
            depr_account_ids = [depr_account.id]  # Can be a list in the future

            asset_account_ids = fixed_asset_account.ids + depr_account_ids
            asset_account_ids_str = ",".join(map(str, asset_account_ids))
            depr_account_ids_str = ",".join(map(str, depr_account_ids))

            sql = f"""
                SELECT fixed_asset_id
                FROM ab_accounting_je_line je
                JOIN ab_accounting_account_guide gu ON je.account_id = gu.id
                JOIN ab_fixed_asset_assets_inventory fa on fa.id = je.fixed_asset_id
                WHERE gu.id IN ({asset_account_ids_str}) and je.active = True and fa.useful_life > 0
                GROUP BY fixed_asset_id
                HAVING SUM(
                    CASE
                        WHEN gu.id IN ({depr_account_ids_str}) THEN je.credit_val - je.debit_val
                        ELSE je.debit_val - je.credit_val
                    END
                ) > 1
            """
            self.env.cr.execute(sql)
            active_asset_ids = [row[0] for row in self.env.cr.fetchall()]

            if value == 'active':
                matched_ids = active_asset_ids
            else:
                all_recs = self.sudo().search([
                    ('je_count', '>', 0),
                    ('id', 'not in', active_asset_ids)
                ])
                matched_ids = [rec.id for rec in all_recs if rec.asset_status == value]

        return [('id', 'not in' if operator == '!=' else 'in', matched_ids)]

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

    @api.depends('je_line_ids')
    def _compute_last_depreciation_date(self):
        depr_account = self.env.ref('ab_accounting.ab_accounting_account_guide_depreciation')

        for rec in self:
            je_line = self.env['ab_accounting_je_line'].search(
                [('fixed_asset_id', '=', rec.id), ('account_id', '=', depr_account.id)],
                limit=1,
                order='due_date desc')

            rec.last_depreciation_date = je_line.due_date

    @api.depends('je_line_ids')
    def _compute_asset_has_accounting_value(self):
        for rec in self:
            JE = self.env['ab_accounting_je_line'].sudo()
            je_lines_count = JE.search_count(
                [('fixed_asset_id', '=', rec.id), ('account_id.internal_type', '=', 'fixed_asset')])
            if je_lines_count > 0:
                rec.asset_has_accounting_value = True
            else:
                rec.asset_has_accounting_value = False

    def _search_asset_has_accounting_value(self, operator, val):
        # Odoo 19 canonicalizes Boolean searches to membership domains.
        if operator in ('in', 'not in'):
            values = set(val)
            if not values or values == {False, True}:
                matches_all = bool(values) == (operator == 'in')
                return [(1, '=', 1)] if matches_all else [(0, '=', 1)]
            val = True in values
            operator = '=' if operator == 'in' else '!='
        if operator not in ['=', '!='] or not isinstance(val, bool):
            raise UserError(_('Operation not supported'))

        self.env.cr.execute(" select fixed_asset_id "
                            " from ab_accounting_je_line je"
                            " join ab_accounting_account_guide gu on gu.id = je.account_id"
                            " WHERE gu.internal_type='fixed_asset' and je.fixed_asset_id IS NOT NULL "
                            " group by je.fixed_asset_id ")
        ids = [row[0] for row in self.env.cr.fetchall()]

        if operator != '=':  # that means it is '!='
            val = not val
        return [('id', 'in' if val else 'not in', ids)]

    def _search_last_depreciation_date(self, operator, val):
        print(operator)
        print(val)
        return []

    @api.depends('je_line_ids', 'je_line_ids.account_id')
    def _compute_total_depr(self):
        for rec in self:
            depr_account = self.env.ref('ab_accounting.ab_accounting_account_guide_depreciation')

            depr_jes = self.env['ab_accounting_je_line'].search(
                [('fixed_asset_id', '=', rec.id), ('account_id', '=', depr_account.id)],
                order='due_date')

            rec.total_depr = sum(je.debit_val - je.credit_val for je in depr_jes)

    @api.depends('je_line_ids', 'je_line_ids.account_id')
    def _compute_current_value_after_depr(self):
        for rec in self:
            rec.current_value_after_depr = rec.asset_total_value - rec.total_depr

    @api.depends('je_line_ids', 'je_line_ids.account_id.internal_type')
    def _compute_asset_total_value(self):
        for rec in self:
            fixed_asset_account = self.env['ab_accounting_account_guide'].search(
                [('internal_type', '=', 'fixed_asset')])

            fixed_asset_jes = self.env['ab_accounting_je_line'].search(
                [('fixed_asset_id', '=', rec.id), ('account_id', 'in', fixed_asset_account.ids)],
                order='due_date')

            rec.asset_total_value = sum(je.debit_val - je.credit_val for je in fixed_asset_jes)

    @api.depends('useful_life')
    def _get_depreciation_rate(self):
        for rec in self:
            if rec.useful_life:
                rec.depreciation_rate = 1 / rec.useful_life * 100

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
        # get standard_ids from final_level
        # because of delegate=True, you can not access final_level properties directly
        # you should use ._origin for that
        # (asset.final_level object) with id=59 will be like ab_fixed_asset_final_level(<NewId origin=59>,)
        standards_ids = asset.final_level._origin.mapped('standards_ids').mapped('id')

        # make object of type model 'ab_fixed_asset_inventory_standards'
        inventory_standards = self.env['ab_fixed_asset_inventory_standards']

        # This for loop will create standard_ids in model_ab_fixed_asset_inventory_standards
        # which is in One2many relation with asset_inventory
        for standard_id in standards_ids:
            inventory_standard = asset.inventory_standards_ids.create({'standard_id': standard_id})
            inventory_standards += inventory_standard

        # Write -in current asset inventory record- the previous standard_ids
        # NOTE THAT it write INVENTORY_STANDARD_IDS not just STANDARD_IDS
        # If you want to know the difference just uncomment the below print line
        asset.write({'inventory_standards_ids': [(6, 0, inventory_standards.ids)]})

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

    def btn_depreciate(self, remove=False):
        sudo_self = self.sudo()
        today = datetime.date.today()

        accum_depr_account = sudo_self.env.ref('ab_accounting.ab_accounting_account_guide_accumulated_depreciation')
        account_fixed_asset = self.env.ref('ab_accounting.ab_accounting_account_guide_fixed_asset')
        depr_account = sudo_self.env.ref('ab_accounting.ab_accounting_account_guide_depreciation')

        fixed_asset_account = sudo_self.env['ab_accounting_account_guide'].search(
            [('internal_type', '=', 'fixed_asset')])

        depr_jes = sudo_self.env['ab_accounting_je_line'].search(
            [('fixed_asset_id', '=', sudo_self.id), ('account_id', '=', depr_account.id)],
            order='due_date')

        fixed_asset_jes = sudo_self.env['ab_accounting_je_line'].search(
            [('fixed_asset_id', '=', sudo_self.id), ('account_id', 'in', fixed_asset_account.ids)],
            order='due_date')

        if not fixed_asset_jes:
            raise ValidationError(_("You can't depreciate if fixed asset je does not exist."))

        asset_value = sum(je.debit_val - je.credit_val for je in fixed_asset_jes)
        asset_purchase_date = fixed_asset_jes[0].due_date

        total_prev_depr = sum(je.debit_val - je.credit_val for je in depr_jes)

        elapsed_days_asset_purchase_date = (today - asset_purchase_date).days
        if self.useful_life:
            all_depr_percent = elapsed_days_asset_purchase_date / (self.useful_life * 365)
            all_depr_value = all_depr_percent * asset_value
            curr_depr_value = all_depr_value - total_prev_depr
        else:
            curr_depr_value = asset_value - total_prev_depr

        if (abs(curr_depr_value) < 1) and (self.asset_total_value > 1):
            raise ValidationError(_("Depreciation is nearly zero for ID (%d)!\nDepreciation is cancelled.") % self.id)
        elif curr_depr_value > 0:
            debit_val = round(curr_depr_value, 2)
            credit_val = 0
        else:
            debit_val = 0
            credit_val = round(curr_depr_value * -1, 2)

        if remove and self.asset_total_value < 1:
            raise ValidationError(_("Asset ID %d already removed (Zero Value)") % self.id)

        lines = [
            (0, 0, {
                'fixed_asset_id': self.id,
                'account_id': depr_account.id,
                'store_id': self.current_store_id.id,
                'debit_val': debit_val,
                'credit_val': credit_val,
                'due_date': datetime.date.today(),
                'explain': f'Depreciation due to {elapsed_days_asset_purchase_date} days',
            }),
            (0, 0, {
                'fixed_asset_id': self.id,
                'account_id': accum_depr_account.id if self.asset_total_value else account_fixed_asset.id,
                'store_id': self.current_store_id.id,
                'debit_val': credit_val,
                'credit_val': debit_val,
                'due_date': today,
                'explain': f'Depreciation due to {elapsed_days_asset_purchase_date} days',
            }),

        ]
        header_je = self.env['ab_accounting_je_header'].create({
            'account_id': accum_depr_account.id,
            'doctype_id': 7,
            'is_posted': True,
            'line_ids': lines})

        if remove:
            header_je.write({'line_ids': [
                (0, 0, {
                    'fixed_asset_id': self.id,
                    'account_id': account_fixed_asset.id,
                    'store_id': self.current_store_id.id,
                    'debit_val': 0.0,
                    'credit_val': self.asset_total_value,
                    'due_date': today,
                    'explain': 'Removed',
                }),
                (0, 0, {
                    'fixed_asset_id': self.id,
                    'account_id': accum_depr_account.id,
                    'store_id': self.current_store_id.id,
                    'debit_val': self.asset_total_value,
                    'credit_val': 0.0,
                    'due_date': today,
                    'explain': 'Removed',
                }),

            ]})

        header_je.sudo_confirm_all_je()

        # if self.asset_total_value < 1 and self.current_value_after_depr < 1:
        #     raise ValidationError(_("You can't depreciate if value after depr. not grater than 0!"))

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
        self.send_by_bot(self.get_chat_id("telegram_fixed_asset_move_group_chat_id"),
                         msg=msg, after=after)
        return res
