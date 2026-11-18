import datetime

from odoo import api, fields, models, _, Command
from odoo.tools.float_utils import float_compare
from markupsafe import Markup, escape
from odoo.exceptions import ValidationError, UserError
from lxml import etree


class AbFixedAssetInventoryLine(models.Model):
    _name = 'ab_fixed_asset_inventory_transfer_line'
    _description = 'ab_fixed_asset_inventory_transfer_line'

    wizard_id = fields.Many2one('ab_fixed_asset_move_wizard', required=True)
    line_id = fields.Many2one('ab_fixed_asset_inventory_line', required=True)
    name = fields.Char(related='line_id.name')
    qty = fields.Integer(related='line_id.qty')
    price = fields.Float(related='line_id.price')
    transfer_qty = fields.Integer(default=1)


    @api.constrains('transfer_qty')
    def _check_transfer_qty(self):
        if any(line.transfer_qty <= 0 for line in self):
            raise ValidationError(_('Transfer quantities must be positive.'))

    @api.model_create_multi
    def create(self, vals_list):
        wizards = self.env['ab_fixed_asset_move_wizard'].browse([vals['wizard_id'] for vals in vals_list if vals.get('wizard_id')])
        self.env['ab_fixed_asset_assets_inventory']._lock_workflow_rows(wizards)
        if any(wizards.mapped('is_submitted')):
            raise UserError(_('Submitted movement lines cannot be changed.'))
        return super().create(vals_list)

    def write(self, vals):
        wizards = self.wizard_id | self.env['ab_fixed_asset_move_wizard'].browse(vals.get('wizard_id', []))
        self.env['ab_fixed_asset_assets_inventory']._lock_workflow_rows(wizards)
        if any(wizards.mapped('is_submitted')):
            raise UserError(_('Submitted movement lines cannot be changed.'))
        return super().write(vals)

    def unlink(self):
        self.env['ab_fixed_asset_assets_inventory']._lock_workflow_rows(self.wizard_id)
        if any(self.wizard_id.mapped('is_submitted')):
            raise UserError(_('Submitted movement lines cannot be changed.'))
        return super().unlink()


class AbFixedAsseInvMoveWizard(models.Model):
    _name = 'ab_fixed_asset_move_wizard'
    _description = 'ab_fixed_asset_move_wizard'
    _order = 'id desc'
    _inherit = ['mail.thread', 'abdin_telegram']

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        result = super().get_view(view_id, view_type, **options)
        if view_type != 'form':
            return result
        hidden = set()
        if not self.env['ab_accounting_je_header'].has_access('read'):
            hidden.add('journal_ids')
        if not self.env['ab_fixed_asset_inventory_transfer_line'].has_access('read'):
            hidden.add('src_inventory_line_transfer_ids')
        if not self.env['ab_costcenter'].has_access('read'):
            hidden.update(('new_costcenter_id', 'remove_costcenter'))
        if hidden:
            # Work on this response after the shared cache, never on the cached
            # architecture. Existing ACLs/rules still govern every operation.
            arch = etree.fromstring(result['arch'])
            for node in arch.xpath('//field | //label'):
                if node.get('name') in hidden or node.get('for') in hidden:
                    node.getparent().remove(node)
            result['arch'] = etree.tostring(arch, encoding='unicode')
        return result

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

    journal_ids = fields.Many2many('ab_accounting_je_header', string='Posted Journals', readonly=True, copy=False)

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
    scrapping_value = fields.Float(default=0, help='Estimated scrap value for reference. Record sale proceeds separately.')
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
            raise ValidationError(_('Access Denied!, Only Fixed Asset Accountant can confirm!'))
        with self.env.cr.savepoint():
            self.env['ab_fixed_asset_assets_inventory']._lock_workflow_rows(self)
            for rec in self:
                if rec.is_confirmed:
                    raise ValidationError(_('Already Confirmed!'))
                if not rec.is_submitted:
                    raise ValidationError(_('Must be submitted first!'))
                super(AbFixedAsseInvMoveWizard, rec.sudo()).write({'is_confirmed': True})
        return True

    def btn_submit(self):
        if not self.env.user.has_group('ab_fixed_asset.group_ab_fixed_asset_manager'):
            raise ValidationError(_('Access Denied!, Only Fixed Asset Manager can submit!'))
        self = self.sudo()
        with self.env.cr.savepoint():
            assets = self.env['ab_fixed_asset_assets_inventory']
            assets._lock_workflow_rows(self)
            involved = self.src_fixed_asset_ids | self.dest_fixed_asset_id
            assets._lock_workflow_rows(involved)
            assets._lock_workflow_rows(self.src_inventory_line_transfer_ids.line_id)
            self.env.invalidate_all()
            for rec in self.sorted('id'):
                rec._validate_submission()
                rec._start_move_type_action()
                rec._notify_action(', '.join(rec.src_fixed_asset_ids.mapped('display_name')))
        return True

    def _validate_submission(self):
        self.ensure_one()
        if self.is_submitted or self.journal_ids:
            raise ValidationError(_('Already submitted!'))
        if not self.src_fixed_asset_ids:
            raise ValidationError(_('Select at least one source asset.'))
        if self.move_type in ('location_move', 'damage_maintenance', 'scrapping') and not self.dest_store_id:
            raise ValidationError(_('Select a destination store.'))
        if self.new_costcenter_id and self.remove_costcenter:
            raise ValidationError(_('Set or Remove costcenter, not both!'))
        if self.move_type == 'change_useful_life':
            if not self.extra_useful_life or any(asset.useful_life + self.extra_useful_life <= 0 for asset in self.src_fixed_asset_ids):
                raise ValidationError(_('The revised useful life must be positive and different from the current life.'))
        if self.move_type not in ('partially_transfer', 'partially_depr'):
            return
        if len(self.src_fixed_asset_ids) != 1:
            raise ValidationError(_('Only one asset can be partially transferred or depreciated'))
        source = self.src_fixed_asset_ids
        if self.move_type == 'partially_transfer':
            if not self.dest_fixed_asset_id or self.dest_fixed_asset_id == source:
                raise ValidationError(_('Select a destination asset different from the source asset.'))
        if not self.partially_explain:
            raise ValidationError(_('Enter an explanation for this adjustment.'))
        if self.je_src_credit_value <= 0 or self.je_dst_debit_value < 0 or self.je_dst_debit_value > self.je_src_credit_value:
            raise ValidationError(_('Adjustment values must be positive and cannot increase the transferred value.'))
        if self.move_type == 'partially_depr' and self.je_dst_debit_value:
            raise ValidationError(_('Partial depreciation cannot include a destination value.'))
        if not source.asset_has_accounting_value or float_compare(self.je_src_credit_value, source.current_value_after_depr, precision_digits=2) > 0:
            raise ValidationError(_('The adjustment exceeds the posted remaining asset value.'))
        quantities = {}
        total = 0
        for line in self.src_inventory_line_transfer_ids:
            if line.line_id.fixed_asset_header_id != source:
                raise ValidationError(_('Every transfer line must belong to the selected source asset.'))
            if line.transfer_qty <= 0 or line.price <= 0:
                raise ValidationError(_('Transfer quantities and prices must be positive.'))
            quantities[line.line_id] = quantities.get(line.line_id, 0) + line.transfer_qty
            total += line.transfer_qty * line.price
        if source.asset_type == 'inventory' and not quantities:
            raise ValidationError(_('Select inventory lines for the inventory adjustment.'))
        if any(qty > line.qty for line, qty in quantities.items()):
            raise ValidationError(_('Transfer quantities exceed the available inventory.'))
        if quantities and float_compare(total, self.je_src_credit_value, precision_digits=2):
            raise ValidationError(_('The source value must equal the selected inventory value.'))

    def _start_move_type_action(self):
        self.ensure_one()
        journals = self.env['ab_accounting_je_header']
        for asset in self.src_fixed_asset_ids:
            if self.move_type in ('partially_transfer', 'partially_depr'):
                journals |= self._create_partial_journal(asset)
                continue
            if self.move_type in ('location_move', 'damage_maintenance', 'scrapping'):
                asset.sudo().current_store_id = self.dest_store_id.id
                # Update only the branch on this movement's asset journals,
                # through the existing accounting workflow context.
                asset.sudo().je_line_ids.with_context(sudo_confirm=True).write({
                    'store_id': self.dest_store_id.id,
                })
            if self.move_type in ('scrapping', 'asset_loss'):
                journals |= asset._dispose_asset()
                asset.sudo().write({'useful_life': 0, 'scrapping_value': self.scrapping_value if self.move_type == 'scrapping' else 0})
            if self.move_type == 'change_useful_life':
                asset.sudo().useful_life += self.extra_useful_life
                journals |= asset._depreciate_asset(allow_reversal=True)
            if self.move_type == 'change_basic_data':
                changes = {}
                if self.new_description:
                    changes['description'] = self.new_description
                if self.new_image:
                    changes['image'] = self.new_image
                if self.new_costcenter_id or self.remove_costcenter:
                    changes['costcenter_id'] = self.new_costcenter_id.id
                if changes:
                    asset.sudo().write(changes)
        super(AbFixedAsseInvMoveWizard, self.sudo()).write({
            'journal_ids': [Command.link(journal.id) for journal in journals],
            'is_submitted': True,
        })

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

        self.message_post(body=Markup('<p>%s</p>') % escape(str(dict(self._fields['move_type']._description_selection(self.env)).get(self.move_type)) + ': ' + src_fixed_asset_names))

        # after = f"\n\n<a href='{self.announcement_link}'>Goto Announcement ⏩</a>"
        after = f"\n\nBy {self.env.user.name}\n<a href='{self.fixed_asset_move_link}'>Goto Link ⏩</a>"

        # attachment = self.attachment if self.send_attachment else None
        attachment = None
        self.env['ab_fixed_asset_assets_inventory']._send_asset_notification(
            body, after, attachment=attachment)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _("Submitted Successfully"),
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and any(vals.get('is_submitted') or vals.get('is_confirmed') or vals.get('journal_ids') for vals in vals_list):
            raise UserError(_('Use the submission and confirmation actions to change workflow state.'))
        return super().create(vals_list)

    def write(self, vals):
        allowed_fields = {'message_ids', 'message_follower_ids', 'activity_ids'}
        self.env['ab_fixed_asset_assets_inventory']._lock_workflow_rows(self)
        if not self.env.su and set(vals) & {'is_submitted', 'is_confirmed', 'journal_ids'}:
            raise UserError(_('Use the submission and confirmation actions to change workflow state.'))
        for rec in self:
            if rec.is_submitted and set(vals) - allowed_fields:
                raise UserError(_('This record is read-only. Only chatter is allowed.'))
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

    def _create_partial_journal(self, asset):
        self.ensure_one()
        amounts = []
        remaining = self.je_src_credit_value
        balances = {}
        for line in asset._posted_asset_lines(asset._asset_cost_accounts()):
            balances[line.account_id] = balances.get(line.account_id, 0) + line.debit_val - line.credit_val
        for account, balance in balances.items():
            amount = min(max(balance, 0), remaining)
            if amount:
                amounts.append((asset, account, 0, amount))
                remaining -= amount
        if float_compare(remaining, 0, precision_digits=2) > 0:
            raise ValidationError(_('The adjustment exceeds the posted remaining asset value.'))
        if self.move_type == 'partially_transfer' and self.je_dst_debit_value:
            destination = self.dest_fixed_asset_id
            account = destination._asset_account('fixed_asset_inventory' if destination.asset_type == 'inventory' else 'fixed_asset')
            amounts.append((destination, account, self.je_dst_debit_value, 0))
        loss = self.je_src_credit_value - self.je_dst_debit_value
        if loss:
            amounts.append((asset, asset._asset_account('depreciation'), loss, 0))
        journal = asset._post_asset_journal(amounts, self.partially_explain)
        for line in self.src_inventory_line_transfer_ids:
            line.line_id.qty -= line.transfer_qty
            if self.move_type == 'partially_transfer':
                self.dest_fixed_asset_id.write({'inventory_line_ids': [Command.create({
                    'name': line.name, 'qty': line.transfer_qty, 'price': line.price,
                })]})
        (asset | self.dest_fixed_asset_id).invalidate_recordset()
        return journal
