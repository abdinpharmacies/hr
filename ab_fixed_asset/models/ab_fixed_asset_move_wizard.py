import datetime

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class AbFixedAssetInventoryLine(models.Model):
    _name = 'ab_fixed_asset_inventory_transfer_line'
    _description = 'ab_fixed_asset_inventory_transfer_line'

    wizard_id = fields.Many2one('ab_fixed_asset_move_wizard', required=True)
    line_id = fields.Many2one('ab_fixed_asset_inventory_line', required=True)
    name = fields.Char(related='line_id.name')
    qty = fields.Integer(related='line_id.qty')
    price = fields.Float(related='line_id.price')
    transfer_qty = fields.Integer(default=1)


class AbFixedAsseInvMoveWizard(models.Model):
    _name = 'ab_fixed_asset_move_wizard'
    _description = 'ab_fixed_asset_move_wizard'
    _order = 'id desc'
    _inherit = ['mail.thread', 'abdin_telegram']

    src_fixed_asset_ids = fields.Many2many(
        comodel_name='ab_fixed_asset_assets_inventory',
        relation='ab_fixed_move_assets_inventory_rel',
        column1='move_id',
        column2='asset_id',
        string='Assets')

    src_fixed_asset_ro_ids = fields.Many2many(related='src_fixed_asset_ids', string="Source Assets")

    dest_fixed_asset_id = fields.Many2one('ab_fixed_asset_assets_inventory', string='Destination Asset')
    dest_store_id = fields.Many2one('ab_store', string='To Store')
    dest_asset_useful_life = fields.Integer(related='dest_fixed_asset_id.useful_life',
                                            string='To Asset - Useful Life')
    dest_asset_total_value = fields.Float(related='dest_fixed_asset_id.asset_total_value',
                                          string='To Asset - Total Value')
    dest_asset_total_depr = fields.Float(related='dest_fixed_asset_id.total_depr',
                                         string='To Asset - Total Depr.')

    dest_asset_after_depr = fields.Float(related='dest_fixed_asset_id.current_value_after_depr',
                                         string='To Asset - Value After Depr.')

    notes = fields.Text()

    dest_fixed_asset_line_ids = fields.One2many(related='dest_fixed_asset_id.inventory_line_ids',
                                                string='To Asset Lines', )
    src_fixed_asset_line_ids = fields.One2many(related='src_fixed_asset_ids.inventory_line_ids')

    partially_explain = fields.Text(string="Explain")

    src_inventory_line_transfer_ids = fields.One2many(
        'ab_fixed_asset_inventory_transfer_line',
        'wizard_id',
        string='Inventory Lines')

    is_submitted = fields.Boolean(copy=False, readonly=True)
    is_confirmed = fields.Boolean(copy=False, default=False, readonly=True)
    src_inventory_line_ids = fields.One2many('ab_fixed_asset_inventory_line',
                                             compute='_compute_src_inventory_line_ids',
                                             string='Source Asset Inventory Lines',
                                             readonly=False)

    dst_inventory_line_ids = fields.One2many('ab_fixed_asset_inventory_line',
                                             compute='_compute_dst_inventory_line_ids',
                                             string='Destination Asset Inventory Lines',
                                             readonly=False)
    scrapping_value = fields.Float(default=0)
    extra_useful_life = fields.Integer(default=0)
    je_src_credit_value = fields.Float(digits=(10, 2))
    je_dst_debit_value = fields.Float(compute='_compute_je_dst_debit_value',
                                      store=True, readonly=False,
                                      digits=(10, 2),
                                      )

    # Basic Data
    new_description = fields.Text(string="New Description")
    new_image = fields.Binary()
    new_costcenter_id = fields.Many2one('ab_costcenter')
    remove_costcenter = fields.Boolean(default=False)

    @api.onchange('src_inventory_line_transfer_ids')
    def _onchange_compute_src_credit(self):
        total_inventory = sum(
            line.price * line.transfer_qty
            for line in self.src_inventory_line_transfer_ids
        )

        self.je_src_credit_value = total_inventory

    @api.depends('src_fixed_asset_ids')
    def _compute_src_inventory_line_ids(self):
        for rec in self:
            if rec.src_fixed_asset_ids:
                rec.src_inventory_line_ids = rec.src_fixed_asset_ids[0].inventory_line_ids
            else:
                rec.src_inventory_line_ids = False

    @api.depends('dest_fixed_asset_id')
    def _compute_dst_inventory_line_ids(self):
        for rec in self:
            if rec.dest_fixed_asset_id:
                rec.dst_inventory_line_ids = rec.dest_fixed_asset_id.inventory_line_ids
            else:
                rec.dst_inventory_line_ids = False

    @api.onchange('remove_costcenter')
    def _onchange_costcenter(self):
        if self.remove_costcenter:
            self.new_costcenter_id = False

    move_type = fields.Selection(
        selection=[
            ('location_move', 'Move From Location To Another'),
            ('partially_transfer', 'Partially Transfer'),
            ('partially_depr', 'Partially Depreciation'),
            ('damage_maintenance', 'Maintenance Due to Employee Cause Damage '),
            ('change_useful_life', 'Change Useful Life'),
            ('scrapping', 'Scrapping'),
            ('asset_loss', 'Asset Loss'),
            ('change_basic_data', 'Changing Assets Basic Data'),
        ],
        required=True
    )
    fixed_asset_move_link = fields.Char(compute='_compute_fixed_asset_move_link', compute_sudo=True)

    @api.onchange('move_type')
    def _onchange_move_type(self):
        self.dest_fixed_asset_id = False
        self.dest_store_id = False
        self.scrapping_value = False
        self.extra_useful_life = False
        self.new_description = False
        self.new_image = False

        if self.move_type == 'change_useful_life':
            self.extra_useful_life = 1

    @api.depends('je_src_credit_value', 'move_type')
    def _compute_je_dst_debit_value(self):
        for rec in self:
            if rec.move_type == 'partially_transfer':
                rec.je_dst_debit_value = rec.je_src_credit_value
            elif rec.move_type == 'partially_depr':
                rec.je_dst_debit_value = 0
            else:  # may add extra logic in future
                rec.je_dst_debit_value = 0

    def _compute_fixed_asset_move_link(self):
        conf_mo = self.env['ir.config_parameter'].sudo()
        for rec in self:
            base_url = conf_mo.get_param('web.base.url')
            rec.fixed_asset_move_link = f"{base_url}/web#id={rec.id}&model={rec._name}&view_type=form"

    @api.constrains('move_type', 'scrapping_value', 'je_dst_debit_value', 'je_src_credit_value')
    def _constrains_ab_fixed_asset_move_wizard(self):
        for rec in self:
            if rec.move_type in ['partially_transfer', 'partially_depr']:
                if rec.je_src_credit_value < 0 or rec.je_dst_debit_value < 0:
                    raise ValidationError(_("Values can not be negative!"))
                if rec.je_src_credit_value < rec.je_dst_debit_value:
                    raise ValidationError(_("'From Value' must be greater than 'To value'!"))

            if rec.move_type == 'scrapping' and not rec.scrapping_value > 0:
                raise ValidationError(_("Scrapping Value must be greater than 0"))

    def btn_confirm(self):
        if not self.env.user.has_group('ab_fixed_asset.group_ab_fixed_asset_accountant'):
            raise ValidationError(_("Access Denied!, Only Fixed Asset Accountant can confirm!"))
        if self.is_confirmed:
            raise ValidationError(_("Already Confirmed!"))
        if not self.is_submitted:
            raise ValidationError(_("Must be submitted first!"))
        self.sudo().is_confirmed = True

    def btn_submit(self):
        if not self.env.user.has_group('ab_fixed_asset.group_ab_fixed_asset_manager'):
            raise ValidationError(_("Access Denied!, Only Fixed Asset Manager can submit!"))
        if self.is_submitted:
            raise ValidationError(_("Already submitted!"))

        self = self.sudo()
        src_fixed_asset_names = "\n".join(f"<div>{asset.display_name}</div>" for asset in self.src_fixed_asset_ids)

        self._start_move_type_action()
        self._notify_action(src_fixed_asset_names)

    def _start_move_type_action(self):
        for asset in self.src_fixed_asset_ids:
            if self.move_type in ['partially_transfer', 'partially_depr']:
                if len(self.src_fixed_asset_ids) != 1:
                    raise ValidationError(_("Only one asset can be partially transferred or depreciated"))
                self.btn_create_je(asset)
                continue

            if self.move_type in ['location_move', 'damage_maintenance', 'scrapping']:
                asset.current_store_id = self.dest_store_id.id
                asset.je_line_ids.store_id = self.dest_store_id.id
            if self.move_type in ['scrapping', 'asset_loss']:
                asset.useful_life = 0
                asset.btn_depreciate(remove=True)
            if self.move_type == 'change_useful_life':
                asset.useful_life += self.extra_useful_life
                asset.btn_depreciate()
            if self.move_type == 'scrapping':
                asset.scrapping_value = self.scrapping_value

            if self.move_type == 'change_basic_data':
                if self.new_description:
                    asset.description = self.new_description
                if self.new_image:
                    asset.image = self.new_image

                if self.new_costcenter_id and self.remove_costcenter:
                    raise ValidationError(_("Set or Remove costcenter, not both!"))
                if self.new_costcenter_id:
                    asset.costcenter_id = self.new_costcenter_id.id
                if self.remove_costcenter:
                    asset.costcenter_id = False

            asset_scrapping_value = asset.scrapping_value
            if asset.useful_life and asset_scrapping_value:
                asset.scrapping_value = 0

            self.is_submitted = True

    def _notify_action(self, src_fixed_asset_names):
        fields_str = {name: field._description_string(self.env) for name, field in self._fields.items()}
        move_type = dict(self._fields['move_type']._description_selection(self.env)).get(self.move_type)
        body_dict = {
            'move_type': move_type,
            'src_fixed_asset_ids': src_fixed_asset_names,
            'dest_fixed_asset_id': self.dest_fixed_asset_id.display_name or '',
            'dest_store_id': self.dest_store_id.display_name or '',
            'extra_useful_life': self.extra_useful_life,
            'scrapping_value': self.scrapping_value,
            'new_description': self.new_description,
        }
        body_dict = {k: v for k, v in body_dict.items() if v}

        # Filtering Truthy values
        body = "".join(f"<div><span class='h6'>{fields_str.get(k, '')}</span>: {v}</div>" for k, v in body_dict.items())
        # if self.move_type == 'change_useful_life':
        #     body += f"<div>Useful Life: {old_useful_life} -> {asset.useful_life}</div>"

        self.message_post(body=body)

        # after = f"\n\n<a href='{self.announcement_link}'>Goto Announcement ⏩</a>"
        after = f"\n\nBy {self.env.user.name}\n<a href='{self.fixed_asset_move_link}'>Goto Link ⏩</a>"

        # attachment = self.attachment if self.send_attachment else None
        attachment = None
        self.send_by_bot(self.get_chat_id("telegram_fixed_asset_move_group_chat_id"),
                         msg=body,
                         after=after,
                         attachment=attachment)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _("Submitted Successfully"),
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def write(self, vals):
        allowed_fields = {'message_ids', 'message_follower_ids', 'activity_ids'}

        for rec in self:
            if not rec.env.su and rec.is_submitted:
                disallowed = set(vals) - allowed_fields
                if disallowed:
                    raise UserError("This record is read-only. Only chatter is allowed.")
        return super().write(vals)

    def name_get(self):
        res = []

        for rec in self:
            move_type = dict(self._fields['move_type']._description_selection(self.env)).get(self.move_type)
            to_destination = rec.dest_fixed_asset_id.display_name or rec.dest_store_id.display_name or ''
            res.append((rec.id, f"{move_type}:{to_destination}"))
        return res

    @api.depends('dest_fixed_asset_id', 'dest_store_id')
    def _compute_display_name(self):
        """Keep the existing label format on the Odoo 19 display-name API."""
        names = dict(self.name_get())
        for record in self:
            record.display_name = names.get(record.id, False)

    def btn_add_src_asset_inventory_line(self):
        if len(self.src_fixed_asset_ids) != 1:
            raise ValidationError(_("Can not add inventory line. Add only for single Source Asset."))
        return {
            'type': 'ir.actions.act_window',
            'name': 'Inventory Line',
            'res_model': 'ab_fixed_asset_inventory_line',
            'view_mode': 'form',
            'target': 'new',  # opens as a modal
            'context': {
                'default_fixed_asset_header_id': self.src_fixed_asset_ids[0].id,
            },
        }

    def btn_add_dst_asset_inventory_line(self):
        if not self.dest_fixed_asset_id:
            raise ValidationError(_("Must have destination asset to add."))
        return {
            'type': 'ir.actions.act_window',
            'name': 'Inventory Line',
            'res_model': 'ab_fixed_asset_inventory_line',
            'view_mode': 'form',
            'target': 'new',  # opens as a modal
            'context': {
                'default_fixed_asset_header_id': self.dest_fixed_asset_id.id,
            },
        }

    def _reconcile_asset(self, asset):
        today = datetime.date.today()
        explain = self.partially_explain
        fixed_asset_account = self.env.ref('ab_accounting.ab_accounting_account_guide_fixed_asset')
        reconciliation_account = self.env.ref('ab_accounting.ab_accounting_account_guide_fixed_asset_reconcile')
        debit_val = credit_val = asset.current_value_after_depr

        lines = [
            (0, 0, {
                'fixed_asset_id': asset.id,
                'account_id': reconciliation_account.id,
                'store_id': asset.current_store_id.id,
                'debit_val': debit_val,
                'credit_val': 0,
                'due_date': today,
                'explain': explain,
            }),
            (0, 0, {
                'fixed_asset_id': asset.id,
                'account_id': fixed_asset_account.id,
                'store_id': asset.current_store_id.id,
                'debit_val': 0,
                'credit_val': credit_val,
                'due_date': today,
                'explain': explain,
            }),
        ]

        header_je = self.env['ab_accounting_je_header'].create({
            'account_id': fixed_asset_account.id,
            'doctype_id': 7,
            'is_posted': True,
            'line_ids': lines
        })

        header_je.sudo_confirm_all_je()

    def btn_create_je(self, asset):
        today = datetime.date.today()
        explain = self.partially_explain
        fixed_asset_debit_account = self.env.ref('ab_accounting.ab_accounting_account_guide_fixed_asset')
        depr_account = self.env.ref('ab_accounting.ab_accounting_account_guide_depreciation')
        fixed_asset_credit_account = fixed_asset_debit_account
        if asset.asset_type == 'inventory':
            fixed_asset_credit_account = self.env.ref('ab_accounting.ab_accounting_account_guide_fixed_asset_inventory')

        credit_val = self.je_src_credit_value
        debit_val = self.je_dst_debit_value
        depreciation_value = credit_val - debit_val

        lines = [
            (0, 0, {
                'fixed_asset_id': self.dest_fixed_asset_id.id,
                'account_id': fixed_asset_debit_account.id,
                'store_id': self.dest_fixed_asset_id.current_store_id.id,
                'debit_val': debit_val,
                'credit_val': 0,
                'due_date': today,
                'explain': explain,
            }),
            (0, 0, {
                'fixed_asset_id': asset.id,
                'account_id': fixed_asset_credit_account.id,
                'store_id': asset.current_store_id.id,
                'debit_val': 0,
                'credit_val': credit_val,
                'due_date': today,
                'explain': explain,
            }),
        ]

        if depreciation_value:
            lines.append(
                (0, 0, {
                    'fixed_asset_id': asset.id,
                    'account_id': depr_account.id,
                    'store_id': asset.current_store_id.id,
                    'debit_val': depreciation_value,
                    'credit_val': 0,
                    'due_date': today,
                    'explain': explain,
                })
            )
        header_je = self.env['ab_accounting_je_header'].create({
            'account_id': fixed_asset_credit_account.id,
            'doctype_id': 7,
            'is_posted': True,
            'line_ids': lines
        })

        header_je.sudo_confirm_all_je()

        for line in self.src_inventory_line_transfer_ids:
            line.line_id.qty -= line.transfer_qty
            self.dest_fixed_asset_id.write({
                'inventory_line_ids': [(0, 0, {
                    'name': line.name,
                    'qty': line.transfer_qty,
                    'price': line.price})]
            })
