# -*- coding: utf-8 -*-
import math

from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import UserError, ValidationError



class AbdinSalesReturnHeader(models.Model):
    _name = 'ab_sales_return_header'
    _description = 'E-Plus Sales Return Header'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'id'
    _order = 'id desc'

    # Original invoice number in B-Connect (sales_trans_h.sth_id).
    origin_header_id = fields.Integer(
        string="Invoice Number",
        default=False,
        help="Original invoice STH ID in B-Connect (sales_trans_h.sth_id).",
    )

    # Store selector used to resolve target server/IP.
    store_id = fields.Many2one(
        'ab_store', required=True,
        domain=lambda self: self._get_allowed_store_domain(),
        default=lambda self: self._default_sales_store_id(),
    )

    sto_eplus_serial = fields.Integer(
        string="Store",
        related='store_id.eplus_serial',
        store=True,
        readonly=True,
    )

    @api.model
    def _get_allowed_store_domain(self):
        domain = [("allow_sale", "=", True)]
        store_ids = self.env['ab_sales_header']._get_allowed_store_ids()
        if store_ids:
            domain.append(("id", "in", store_ids))
        return domain

    @api.model
    def _default_sales_store_id(self):
        default_store_id = self.env['ab_sales_header']._get_default_store_id()
        return default_store_id

    # Document status.
    status = fields.Selection(
        selection=[('prepending', 'PrePending'),
                   ('pending', 'Pending'),
                   ('saved', 'Saved')],
        default='prepending')

    line_ids = fields.One2many(
        'ab_sales_return_line',
        'header_id',
        string="Return Lines",
    )

    total_return_qty = fields.Float(
        string="Total Qty",
        compute='_compute_totals',
        store=True,
    )
    total_return_value = fields.Float(
        string="Total Value",
        compute='_compute_totals',
        store=True,
    )

    # SQL output ids captured after posting.
    sales_return_id = fields.Integer(
        string="sales_return ID (sr_id)"
    )
    f_transaction_id = fields.Integer(
        string="F-Transaction_Header ID (fh_id)",
        help="Primary key from F_Transaction_Header table."
    )

    total_sales_net = fields.Float(readonly=True)

    notes = fields.Text(string="Notes")

    # ------------------------ helpers ------------------------

    @api.depends('line_ids.qty', 'line_ids.sell_price', 'line_ids.max_returnable_qty', 'total_sales_net')
    def _compute_totals(self):
        for rec in self:
            qty = 0.0
            val = 0.0
            for line in rec.line_ids:
                qty += line.qty or 0.0
                val += (line.qty or 0.0) * (line.sell_price or 0.0)
            rec.total_return_qty = qty
            if rec._is_total_return_invoice():
                rec.total_return_value = float(rec.total_sales_net or 0.0)
            else:
                rec.total_return_value = val

    def _is_total_return_invoice(self):
        self.ensure_one()
        if not self.line_ids:
            return False
        return all(
            math.isclose(
                float(line.qty or 0.0),
                float(line.max_returnable_qty or 0.0),
                rel_tol=0.0,
                abs_tol=1e-4,
            )
            for line in self.line_ids
        )


    @staticmethod
    def _find_uom_by_factor(product, factor, preferred_uom_id=False):
        if not product:
            return False
        if preferred_uom_id:
            preferred = product.env["ab_product_uom"].browse(int(preferred_uom_id)).exists()
            if preferred and preferred.category_id == product.uom_category_id:
                return preferred
        if not product.uom_category_id:
            return product.uom_id
        candidates = product.env["ab_product_uom"].search([("category_id", "=", product.uom_category_id.id)])
        if not candidates:
            return product.uom_id
        if factor and factor > 0:
            for uom in candidates:
                if math.isclose(float(uom.factor or 0.0), float(factor), rel_tol=0.0, abs_tol=1e-5):
                    return uom
        return product.uom_id or candidates[:1]


    def action_clear_lines(self):
        self.line_ids.unlink()

    def action_total_return_invoice(self):
        self.ensure_one()
        if self.status == 'saved':
            raise UserError(_("Saved returns cannot be modified."))
        if not self.line_ids:
            self.action_load_lines()
        for line in self.line_ids:
            line.write({
                'qty_str': line._fmt_qty(line.max_returnable_qty or 0.0),
            })
        self._compute_totals()
        return True

    def action_set_pending(self):
        for rec in self:
            if rec.status == 'saved':
                raise UserError(_("Saved returns cannot be moved back to pending."))
            if rec.status == 'pending':
                continue
            if rec.status != 'prepending':
                raise UserError(_("Only prepending returns can be moved to pending."))
            rec._validate_return()
            rec.status = 'pending'
        return True


    def _validate_return(self):
        """Validate quantities before push."""
        if self.status == 'saved':
            raise UserError(_("Already Saved"))
        if not self.line_ids:
            raise UserError(_("No lines to return."))

        total_source = 0.0
        for line in self.line_ids:
            qty_selected = float(line.qty or 0.0)
            if qty_selected < 0:
                raise UserError(
                    _("Return quantity cannot be negative for product %s.")
                    % (line.product_id.display_name or line.itm_eplus_id)
                )
            if qty_selected and qty_selected > float(line.max_returnable_qty or 0.0):
                raise UserError(
                    _("Return qty for product %s exceeds allowed max (%s).")
                    % (line.product_id.display_name or line.itm_eplus_id, line.max_returnable_qty)
                )

            qty_source = float(line._qty_to_source_unit() or 0.0)
            sold_source = float(line.qty_sold_source or line._qty_to_source_unit(line.qty_sold or 0.0))
            if line.itm_nexist and qty_source and not math.isclose(qty_source, sold_source, rel_tol=0.0, abs_tol=1e-4):
                raise UserError(_("Product '%s' is sold without balance.\nMust be returned completely!")
                                % (line.product_id.display_name or str(line.itm_eplus_id or line.id)))

            total_source += qty_source

        if total_source <= 0:
            raise UserError(_("Please enter a positive return quantity on at least one line."))

        target = self.env.context.get('curr_target') or 'current'
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ab_sales_return_header',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'res_id': self.id,
            'target': target,
        }
