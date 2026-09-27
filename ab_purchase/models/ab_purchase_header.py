from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
import re


class AbdinPurchaseHeader(models.Model):
    _name = 'ab_purchase_header'
    _description = "Abdin Purchase Header"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "doc_code"
    _order = "create_date desc"

    supplier_id = fields.Many2one("ab_supplier", required=True, tracking=True, index=True)
    store_id = fields.Many2one("ab_store", required=True, tracking=True, index=True, readonly=True)
    doc_code = fields.Char(required=True, tracking=True)
    doc_date = fields.Date(required=True, default=lambda self: datetime.today(), index=True, tracking=True)
    number_of_products = fields.Integer(compute="compute_totals")
    lines_count = fields.Integer(compute="compute_totals")
    total_price = fields.Float(digits=(16, 3), compute="compute_totals", string="Total Selling Price")
    total_purchase_price = fields.Float(digits=(16, 3), compute="compute_totals")
    total_cost = fields.Float(digits=(16, 3), compute="compute_totals")
    total_tax = fields.Float(digits=(16, 3), compute="compute_totals")
    total_extra_discount_percentage = fields.Float(compute="compute_total_extra_discount_percentage",
                                                   inverse="_inverse_total_extra_discount_percentage")
    net_invoice = fields.Float(digits=(16, 3))
    net_tax = fields.Float(digits=(16, 3))
    active = fields.Boolean(default=True, index=True)
    description = fields.Text(tracking=True)
    net_invoice_eq_total_cost = fields.Boolean(
        default=True,
        store=True,
        index=True,
        readonly=True,
        compute_sudo=True,
        compute='_compute_net_invoice_eq_total_cost')

    status = fields.Selection(
        selection=[
            ("prepending", "PrePending"),
            ("pending", "Pending"),
            ("saved", "Saved"),
            ("rejected", "Rejected")
        ],
        default="prepending",
        index=True,
    )

    invoice_type = fields.Selection(selection=[("medical", "Medical"), ("cosmetics", "Cosmetics"), ("bonus", "Bonus")],
                                    default="medical", required=True)
    line_ids = fields.One2many(comodel_name="ab_purchase_line", inverse_name="header_id", required=True)

    # eplus fields
    eplus_serial = fields.Integer(index=True, readonly=True)

    eplus_total_disc_on_inv = fields.Float(digits=(10, 2), default=0, readonly=True)

    last_update_date = fields.Datetime(index=True, readonly=True)

    total_extra_discount = fields.Float(digits=(16, 3),
                                        store=True,
                                        readonly=False,
                                        compute='_compute_total_extra_discount')

    @api.depends('line_ids.disc_tax_no_effect_value', 'eplus_total_disc_on_inv')
    def _compute_total_extra_discount(self):
        for rec in self:
            rec.total_extra_discount = (sum(rec.line_ids.mapped('disc_tax_no_effect_value'))
                                        + rec.eplus_total_disc_on_inv)

    _eplus_serial_unique = models.Constraint(
        'UNIQUE(eplus_serial)',
        'ePlus Serial CAN NOT BE DUPLICATED!',
    )

    @api.constrains("doc_code")
    def constrains_ab_purchase_header(self):
        if self.env.context.get('eplus_replication'):
            return

        for rec in self:
            if not self.validate_doc_code(rec.doc_code):
                raise ValidationError(
                    _("The invoice number can contain numbers, letters, or dashes")
                )

    @api.depends("total_cost", "total_extra_discount")
    def compute_total_extra_discount_percentage(self):
        for rec in self:
            total_before_discount = rec.total_cost + rec.total_extra_discount
            rec.total_extra_discount_percentage = (
                rec.total_extra_discount / total_before_discount
                if total_before_discount
                else 0.0
            )

    @api.onchange("total_extra_discount_percentage")
    def _inverse_total_extra_discount_percentage(self):
        for rec in self:
            total_before_discount = rec.total_cost + rec.total_extra_discount
            rec.total_extra_discount = (
                    total_before_discount * rec.total_extra_discount_percentage
            )
            rec.update(
                {
                    "total_extra_discount": total_before_discount
                                            * rec.total_extra_discount_percentage
                }
            )

    @api.depends('status', 'net_invoice')
    def _compute_net_invoice_eq_total_cost(self):
        for rec in self:
            if rec.status == 'prepending' or abs(rec.net_invoice - rec.total_cost) <= 2:
                # set to True if (net_invoice_eq_total_cost=False)
                if not rec.net_invoice_eq_total_cost:
                    rec.net_invoice_eq_total_cost = True
            else:
                # set to False if (net_invoice_eq_total_cost=True)
                if rec.net_invoice_eq_total_cost:
                    rec.net_invoice_eq_total_cost = False

    def validate_doc_code(self, doc_code):
        is_matched = re.match(r"^[a-zA-Z0-9-]+$", doc_code)
        return is_matched

    @api.onchange("doc_code", "supplier_id")
    def _onchange_doc_code_supplier_id(self):
        for rec in self:
            if rec.doc_code and rec.supplier_id:
                exists = self.search(
                    [
                        ("doc_code", "=", rec.doc_code),
                        ("supplier_id", "=", rec.supplier_id.id),
                    ],
                    limit=1,
                )
                if exists:
                    msg = f"This invoice entered before by: {exists.create_uid.name}" \
                          f"\nSupplier: {exists.supplier_id.name}"

                    raise UserError(_(msg))
                if not self.validate_doc_code(rec.doc_code):
                    msg = "The invoice number can contain numbers, letters, or dashes"
                    raise UserError(_(msg))

    # def distribution_extra_discount(self):
    #     for line in self.line_ids:
    #         line.source_id.update(
    #             {
    #                 "extra_discount_percentage": self.total_extra_discount_percentage
    #                                              * 100
    #             }
    #         )
    #     self.total_extra_discount = 0.0

    def _validate_ven_invoice(self):
        purchase_details = self.line_ids
        if not purchase_details:
            raise UserError(_("Error: No products found on the supplier invoice."))
        if abs(self.total_cost - self.net_invoice) > 0.5:
            raise UserError(
                _(
                    "Error: Net invoice amount does not match the total cost of the products."
                )
            )

        if abs(self.total_tax - self.net_tax) > 0.5:
            raise UserError(
                _("Error: Net tax amount does not match the total tax of the products.")
            )
        if self.total_cost > self.total_price:
            raise UserError(
                _(
                    "Error: Total cost cannot be equal to or greater than the total selling price of the products."
                )
            )

    # def btn_switch_confirm(self):
    #     for rec in self.line_ids:
    #         rec.confirm = not rec.confirm

    def btn_to_store(self):
        return self.btn_save_inventory()

    @api.model_create_multi
    def create(self, vals_list):
        if any(vals.get('status', 'prepending') != 'prepending' for vals in vals_list):
            raise ValidationError(_("Create purchase invoices as drafts."))
        return super().create(vals_list)

    def write(self, vals):
        if 'status' in vals:
            raise ValidationError(_("Use the purchase inventory actions to change status."))
        return super().write(vals)

    def btn_submit_inventory(self):
        self.ensure_one()
        if not (self.env.user.has_group('base.group_system')
                or self.env.user.has_group('ab_purchase.group_ab_purchase_manager')):
            raise AccessError(_("Only purchase managers can submit invoices for inventory."))
        if not self.line_ids or self.status != 'prepending':
            raise ValidationError(_("Only draft purchase invoices with lines can be submitted."))
        with self.env.cr.savepoint():
            for rec in self.line_ids:
                if rec.qty < 0 or rec.bonus < 0:
                    raise ValidationError(_("Purchase quantities and bonuses cannot be negative."))
                qty_total = rec.qty + rec.bonus
                self.env['ab_inventory_process'].inventory_write(
                    rec, qty_total, self.store_id.id, status='pending',
                )
            super(AbdinPurchaseHeader, self).write({'status': 'pending'})
        return True

    def btn_save_inventory(self):
        self.ensure_one()
        if not (self.env.user.has_group('base.group_system')
                or self.env.user.has_group('ab_purchase.group_ab_purchase_manager')):
            raise AccessError(_("Only purchase managers can save receipts into stock."))
        if self.status == 'saved':
            return True
        if self.status != 'pending' or not self.line_ids:
            raise ValidationError(_("Submit a purchase invoice with lines before receiving stock."))
        with self.env.cr.savepoint():
            for line in self.line_ids:
                if line.qty < 0 or line.bonus < 0:
                    raise ValidationError(_("Purchase quantities and bonuses cannot be negative."))
                self.env['ab_inventory_process'].inventory_write(
                    line, line.qty + line.bonus, self.store_id.id, status='saved',
                )
            super(AbdinPurchaseHeader, self).write({'status': 'saved'})
        return True

    @api.depends("line_ids", "line_ids.line_price", "line_ids.line_cost", "line_ids.line_taxes_value",
                 "line_ids.extra_discount_percentage")
    def compute_totals(self):
        for rec in self:
            rec.total_price = sum(rec.line_price for rec in rec.line_ids)
            rec.total_cost = (sum(rec.line_cost for rec in rec.line_ids) - rec.total_extra_discount)
            rec.total_tax = sum(rec.line_taxes_value for rec in rec.line_ids)
            rec.total_purchase_price = sum(
                rec.line_purchase_price * (1 - rec.extra_discount_percentage / 100) for rec in rec.line_ids)
            rec.number_of_products = sum(rec.qty for rec in rec.line_ids)
            rec.lines_count = self.env['ab_purchase_line'].sudo().search_count([('header_id', '=', rec.id)])
