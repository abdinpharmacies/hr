# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import ValidationError


class TransferHeader(models.Model):
    _name = 'ab_transfer_header'
    _description = 'ab_transfer_header'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'ab_inventory_process']

    store_id = fields.Many2one('ab_store', required=True)
    to_store_id = fields.Many2one('ab_store', required=True)
    total_price = fields.Float(compute='compute_totals')
    number_of_products = fields.Integer(compute='compute_totals')
    description = fields.Text()
    status = fields.Selection(
        selection=[('prepending', 'PrePending'),
                   ('pending', 'Pending'),
                   ('saved', 'Saved'),
                   ('rejected', 'Rejected')],
        default='prepending', required=True)
    line_ids = fields.One2many('ab_transfer_line', 'header_id', required=True)
    transmitted_by = fields.Selection(
        selection=[('delivery', 'Delivery'),
                   ('company_car', 'Company Car'),
                   ('private_car', 'Private Car')],
        default='delivery', required=True)
    delivery_id = fields.Many2one('ab_hr_employee')

    def btn_rejected_all_quantity(self):
        transfer_details = self.line_ids
        for line in transfer_details:
            line.qty_rejected = line.qty
        self.btn_receive_transfer()

    def btn_send_transfer(self):
        inventory = self.env['ab_inventory']
        self._validate_sent_transfer()
        transfer_details = self.line_ids
        for line in transfer_details:
            inventory_line = inventory.search(
                [('model_ref', '=', line._name), ('res_id', '=', line.id)])
            if len(inventory_line) == 0:
                store_id = self.store_id.id
                self.inventory_write(line, line.qty, store_id, status='pending_main', sign=-1)

                to_store_id = self.to_store_id.id
                self.inventory_write(line, line.qty, to_store_id, status='pending_main')

        self.status = 'pending'

    def btn_receive_transfer(self):
        inventory = self.env['ab_inventory']
        self._validate_receive_transfer()
        transfer_details = self.line_ids
        any_qty_rejected = False
        for line in transfer_details:
            qty = line.qty - line.qty_rejected
            status = 'saved' if line.qty_rejected == 0 else 'pending_main'
            inventory_line_from = inventory.search(
                [('model_ref', '=', line._name), ('res_id', '=', line.id), ('store_id', '=', self.store_id.id)])
            inventory_line_to = inventory.search(
                [('model_ref', '=', line._name), ('res_id', '=', line.id), ('store_id', '=', self.to_store_id.id)])
            if len(inventory_line_from) > 0 and len(inventory_line_to) > 0:
                store_id = self.store_id.id
                self.inventory_write(line, qty, store_id, sign=-1, inventory_line=inventory_line_from, status=status)

                store_id = self.to_store_id.id
                self.inventory_write(line, qty, store_id, inventory_line=inventory_line_to, status=status)

            if line.qty_rejected > 0:
                any_qty_rejected = True
        self.status = 'rejected' if any_qty_rejected else 'saved'

    def btn_receive_rejected_quantity(self):
        inventory = self.env['ab_inventory']
        transfer_details = self.line_ids
        for line in transfer_details:
            if line.qty_rejected != 0:
                qty = line.qty - line.qty_rejected
                inventory_line_from = inventory.search(
                    [('model_ref', '=', line._name), ('res_id', '=', line.id),
                     ('store_id', '=', self.store_id.id)])
                inventory_line_to = inventory.search(
                    [('model_ref', '=', line._name), ('res_id', '=', line.id), ('store_id', '=', self.to_store_id.id)])
                if len(inventory_line_from) > 0 and len(inventory_line_to) > 0:
                    store_id = self.store_id.id
                    self.inventory_write(line, qty, store_id, sign=-1, inventory_line=inventory_line_from,
                                         status='pending_main')

                    store_id = self.to_store_id.id
                    self.inventory_write(line, qty, store_id, inventory_line=inventory_line_to, status='pending_main')

        self.status = 'saved'

    @api.depends('line_ids')
    def compute_totals(self):
        for line in self:
            line.total_price = sum(rec.line_price for rec in line.line_ids)
            line.number_of_products = len(line.line_ids)

    @api.onchange('store_id')
    def _onchange_from_store(self):
        for rec in self:
            if self.store_id:
                rec.line_ids = None
                rec.to_store_id = None

    def _validate_sent_transfer(self):
        for rec in self.line_ids:
            balance_per_tracking = sum(
                [line.qty for line in self.line_ids if line.source_id == rec.source_id])
            if balance_per_tracking > rec.balance_per_price:
                raise ValidationError(
                    _("Incorrect quantity The quantity sent cannot be greater than the quantity on tracking"))
            if rec.qty < 0:
                raise ValidationError(
                    _("Invalid quantity The quantity sent cannot be a negative value"))

    def _validate_receive_transfer(self):
        for rec in self.line_ids:
            if rec.qty_rejected < 0:
                raise ValidationError(
                    _("Invalid quantity The rejected quantity cannot be a negative value"))
            if rec.qty_rejected > rec.qty:
                raise ValidationError(
                    _("Incorrect quantity The rejected quantity cannot be greater than the sent quantity"))
