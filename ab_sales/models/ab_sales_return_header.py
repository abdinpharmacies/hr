# -*- coding: utf-8 -*-
import math
from typing import Literal

from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import UserError, ValidationError
import decimal
import logging

_logger = logging.getLogger(__name__)

PARAM_STR = '?'  # Parameter placeholder used in E-Plus SQL.


def _to_native(v):
    """Normalize all values so Odoo never receives Decimal or strange types."""
    if isinstance(v, decimal.Decimal):
        # Keep integral decimals as int, otherwise cast to float.
        if v == v.to_integral():
            return int(v)
        return float(v)
    if v is None:
        return False
    return v


class AbdinSalesReturnHeader(models.Model):
    _name = 'ab_sales_return_header'
    _description = 'E-Plus Sales Return Header'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'ab_eplus_connect']
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
    @staticmethod
    def _get_identity(cur, label="identity"):
        """Read latest identity value in the same DB session."""
        cur.execute("SELECT CAST(@@IDENTITY AS BIGINT)")
        row = cur.fetchone()
        if row and row[0] is not None:
            return int(row[0])
        raise UserError(_("Could not retrieve %s from E-Plus (@@IDENTITY is NULL).") % label)

    @api.depends('line_ids.qty', 'line_ids.sell_price')
    def _compute_totals(self):
        for rec in self:
            qty = 0.0
            val = 0.0
            for line in rec.line_ids:
                qty += line.qty or 0.0
                val += (line.qty or 0.0) * (line.sell_price or 0.0)
            rec.total_return_qty = qty
            rec.total_return_value = val

    @staticmethod
    def _get_invoice_status(cur, sth_id) -> Literal["Not Exist", "Saved", "Pending"]:
        cur.execute(
            f"SELECT sth_flag, sto_id FROM sales_trans_h WHERE sth_id={PARAM_STR}",
            (sth_id,)
        )
        status = cur.fetchone()
        if not status:
            return "Not Exist"
        elif status[0] == 'C':
            return "Saved"
        else:
            return "Pending"

    def _validate_invoice_return_window(self, sth_id):
        """Validate current invoice age against current replica return policy using Odoo create_date."""
        self.ensure_one()
        replica_db = self.env["ab_replica_db"].sudo().get_current_from_config()
        allowed_days = max(1, int((replica_db.return_allowed_days if replica_db else 14) or 14))
        source_header = self.env['ab_sales_header'].sudo().search(
            [
                ('eplus_serial', '=', int(sth_id)),
                ('store_id', '=', self.store_id.id),
            ],
            order='id desc',
            limit=1,
        )
        if not source_header or not source_header.create_date:
            raise UserError(_("Source invoice was not found in Odoo; cannot validate return period."))

        now_date = fields.Datetime.context_timestamp(self, fields.Datetime.now()).date()
        invoice_date = fields.Datetime.context_timestamp(self, source_header.create_date).date()
        invoice_age_days = max((now_date - invoice_date).days, 0)
        if invoice_age_days > allowed_days:
            raise UserError(
                _(
                    "Return not allowed. Invoice age (%s days) exceeded allowed return period (%s days)."
                ) % (invoice_age_days, allowed_days)
            )

    def _get_return_adjustments(self, cur, sth_id, total_value, net_return):
        """
        Hook for inherited modules to customize return posting deltas.
        """
        self.ensure_one()
        return {
            'total_bill_after_disc_delta': float(total_value or 0.0),
            'total_bill_net_delta': float(net_return or 0.0),
            'fcs_current_balance_delta': float(net_return or 0.0),
        }

    @staticmethod
    def _factor_for_itm_unit(itm_unit, unit1_unit2, unit1_unit3):
        try:
            itm_unit = int(itm_unit or 3)
        except Exception:
            itm_unit = 3
        unit1_unit2 = float(unit1_unit2 or 1.0)
        unit1_unit3 = float(unit1_unit3 or 1.0)
        if itm_unit == 1:
            return unit1_unit3 if unit1_unit3 > 0 else 1.0
        if itm_unit == 2:
            return unit1_unit2 if unit1_unit2 > 0 else 1.0
        return 1.0

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

    @staticmethod
    def _to_display_qty(qty_source, source_factor, target_factor):
        source_factor = float(source_factor or 1.0) or 1.0
        target_factor = float(target_factor or 1.0) or 1.0
        return float(qty_source or 0.0) * source_factor / target_factor

    @staticmethod
    def _to_display_price(price_source, source_factor, target_factor):
        source_factor = float(source_factor or 1.0) or 1.0
        target_factor = float(target_factor or 1.0) or 1.0
        return float(price_source or 0.0) * target_factor / source_factor

    def action_clear_lines(self):
        self.line_ids.unlink()

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

    def action_load_lines(self):
        """Load source sales lines from B-Connect and map them to return lines."""
        self.ensure_one()
        if not self.origin_header_id:
            raise UserError(_("Please enter sth_id (Original Invoice) first."))
        if not self.store_id or not self.store_id.ip1:
            raise UserError(_("Please select a Store with IP before loading invoice."))
        if self.line_ids and self.line_ids[0].sth_id != self.origin_header_id:
            raise UserError(_("You try to call another Invoice, Please clear the old one!"))

        ReturnLine = self.env['ab_sales_return_line'].sudo()
        Product = self.env['ab_product'].sudo()
        SalesHeader = self.env['ab_sales_header'].sudo()
        Uom = self.env['ab_product_uom'].sudo()

        conn = self.get_connection()
        if not conn:
            raise UserError(_("Connection to B-Connect failed."))

        eplus_lines = []
        sth_id = int(self.origin_header_id or 0)

        try:
            cur = conn.cursor()
            cur.execute(
                f"SELECT total_bill_net FROM sales_trans_h WHERE sth_id = {PARAM_STR}",
                (sth_id,),
            )
            row = cur.fetchone()
            if not row:
                raise UserError(_("Invoice %s not found in B-Connect.") % sth_id)
            self.total_sales_net = float(row[0] if row[0] is not None else 0.0)

            cur.execute(
                f"""
                    SELECT std_id, itm_id, c_id, qnty, itm_unit, itm_sell, itm_cost, itm_aver_cost, itm_back, itm_nexist
                    FROM sales_trans_d
                    WHERE sth_id={PARAM_STR}
                    ORDER BY std_id
                """,
                (sth_id,),
            )
            rows = cur.fetchall()
            if not rows:
                raise UserError(_("Invoice %s has no lines in B-Connect.") % sth_id)

            item_ids = list({int(_to_native(r[1]) or 0) for r in rows if r and _to_native(r[1])})
            unit_map = {}
            if item_ids:
                placeholders = ",".join([PARAM_STR] * len(item_ids))
                cur.execute(
                    f"""
                        SELECT itm_id, ISNULL(itm_unit1_unit2,1), ISNULL(itm_unit1_unit3,1)
                        FROM item_catalog
                        WHERE itm_id IN ({placeholders})
                    """,
                    tuple(item_ids),
                )
                unit_map = {
                    int(itm_id): (float(unit12 or 1.0), float(unit13 or 1.0))
                    for itm_id, unit12, unit13 in cur.fetchall()
                    if itm_id
                }

            source_header = SalesHeader.search(
                [
                    ('eplus_serial', '=', sth_id),
                    ('store_id', '=', self.store_id.id),
                ],
                order='id desc',
                limit=1,
            )
            source_uom_by_item = {}
            if source_header:
                for source_line in source_header.line_ids:
                    serial = int(source_line.product_id.eplus_serial or 0) if source_line.product_id else 0
                    if not serial or serial in source_uom_by_item:
                        continue
                    if source_line.uom_id:
                        source_uom_by_item[serial] = int(source_line.uom_id.id)

            for std_id, itm_id, c_id, qnty, itm_unit, itm_sell, itm_cost, itm_aver_cost, itm_back, itm_nexist in rows:
                sold_qty_source = float(_to_native(qnty))
                itm_id_native = int(_to_native(itm_id))
                std_id_native = int(_to_native(std_id))
                itm_back_native = float(_to_native(itm_back))
                itm_nexist_native = float(_to_native(itm_nexist))
                itm_unit_native = int(_to_native(itm_unit) or 3)

                max_return_source = max(sold_qty_source - itm_back_native, 0.0)
                unit12, unit13 = unit_map.get(itm_id_native, (1.0, 1.0))
                source_factor = self._factor_for_itm_unit(itm_unit_native, unit12, unit13)

                product = Product.search([('eplus_serial', '=', itm_id_native)], limit=1)
                preferred_uom_id = source_uom_by_item.get(itm_id_native)
                uom = self._find_uom_by_factor(product, source_factor, preferred_uom_id=preferred_uom_id)
                target_factor = float(uom.factor or source_factor or 1.0) if uom else float(source_factor or 1.0)

                sell_source = float(_to_native(itm_sell))
                cost_source = float(_to_native(itm_aver_cost if itm_aver_cost is not None else itm_cost))

                eplus_lines.append(
                    {
                        'sale_line_id': std_id_native,
                        'product_id': product.id,
                        'uom_id': uom.id if uom else False,
                        'source_itm_unit': itm_unit_native,
                        'source_uom_factor': source_factor,
                        'item_unit1_unit2': unit12,
                        'item_unit1_unit3': unit13,
                        'qty_sold_source': sold_qty_source,
                        'max_returnable_source': max_return_source,
                        'qty_sold': self._to_display_qty(sold_qty_source, source_factor, target_factor),
                        'max_returnable_qty': self._to_display_qty(max_return_source, source_factor, target_factor),
                        'sell_price': self._to_display_price(sell_source, source_factor, target_factor),
                        'cost': self._to_display_price(cost_source, source_factor, target_factor),
                        'itm_eplus_id': itm_id_native,
                        'sth_id': sth_id,
                        'sto_id': int(self.sto_eplus_serial or 0),
                        'c_id': int(_to_native(c_id)),
                        'std_id': std_id_native,
                        'itm_nexist': itm_nexist_native,
                    }
                )
        finally:
            pass

        for vals in eplus_lines:
            existing = ReturnLine.search(
                [
                    ('sth_id', '=', vals['sth_id']),
                    ('std_id', '=', vals['std_id']),
                    ('header_id', '=', self.id),
                ],
                limit=1,
            )
            vals_db = dict(vals, header_id=self.id)
            if existing:
                selected_uom = existing.uom_id or (
                        vals_db.get('uom_id') and Uom.browse(vals_db['uom_id']).exists()
                )
                source_factor = float(vals_db.get('source_uom_factor') or 1.0) or 1.0
                if selected_uom:
                    target_factor = float(selected_uom.factor or source_factor or 1.0) or 1.0
                    default_factor = source_factor
                    if vals.get('uom_id'):
                        default_uom = Uom.browse(vals['uom_id']).exists()
                        if default_uom:
                            default_factor = float(default_uom.factor or source_factor or 1.0) or source_factor
                    vals_db['uom_id'] = int(selected_uom.id)
                    vals_db['qty_sold'] = self._to_display_qty(vals_db.get('qty_sold_source', 0.0), source_factor,
                                                               target_factor)
                    vals_db['max_returnable_qty'] = self._to_display_qty(vals_db.get('max_returnable_source', 0.0),
                                                                         source_factor, target_factor)
                    source_sell = float(vals_db.get('sell_price') or 0.0) * source_factor / max(default_factor, 1e-9)
                    source_cost = float(vals_db.get('cost') or 0.0) * source_factor / max(default_factor, 1e-9)
                    vals_db['sell_price'] = self._to_display_price(source_sell, source_factor, target_factor)
                    vals_db['cost'] = self._to_display_price(source_cost, source_factor, target_factor)
                existing.write(vals_db)
            else:
                ReturnLine.create(vals_db)

        target = self.env.context.get('curr_target') or 'current'
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ab_sales_return_header',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'res_id': self.id,
            'target': target,
        }

    def action_push_to_eplus_return(self):
        """
        Execute return on B-Connect with UoM-aware posting.
        """
        replica_db = self.env["ab_replica_db"].sudo().get_current_from_config()
        if not replica_db:
            raise UserError(_("This is not Replica DB"))
        self.ensure_one()
        self.action_load_lines()
        self._validate_return()
        if not self.line_ids:
            raise UserError(_("No lines to return."))

        total_sold_qty_source = sum(
            float(line.qty_sold_source or line._qty_to_source_unit(line.qty_sold or 0.0))
            for line in self.line_ids
        )
        total_return_qty_source = 0.0

        conn = self.get_connection()
        if not conn:
            raise UserError(_("Connection to B-Connect failed."))

        try:
            cur = conn.cursor()
            sth_id = int(self.origin_header_id or 0)

            invoice_status = self._get_invoice_status(cur, sth_id)
            if invoice_status == 'Not Exist':
                raise UserError(_("Invoice does not Exist"))
            elif invoice_status == 'Pending':
                raise UserError(
                    _("Source sales invoice #%s is still pending. Save the source invoice first, then push the return.")
                    % sth_id
                )

            self._validate_invoice_return_window(sth_id=sth_id)

            emp_id = self.env['ab_sales_header']._get_eplus_emp_id()
            if not emp_id:
                raise UserError("Employee has no eplus_serial to use! please contact support")

            fcs_id = 1
            pc_name = self.env.user.login or 'ODOO'

            total_qty = 0.0
            total_value = 0.0

            for line in self.line_ids:
                if line.qty <= 0:
                    continue

                q_back_source = float(line._qty_to_source_unit())
                if q_back_source <= 0:
                    continue

                itm_id = int(line.itm_eplus_id or 0)
                c_id = int(line.c_id or 0)
                std_id = int(line.std_id or 0)
                sto_id = int(line.sto_id or self.sto_eplus_serial or 0)
                is_nexist = bool(line.itm_nexist)
                missing_base_keys = (not itm_id) or (not std_id) or (not sto_id)
                allow_zero_c_id = is_nexist
                if (not c_id) and (not allow_zero_c_id) and itm_id and sto_id:
                    cur.execute(
                        f"""
                            SELECT COUNT(1)
                            FROM Item_Class_Store
                            WHERE itm_id = {PARAM_STR} AND sto_id = {PARAM_STR}
                        """,
                        (itm_id, sto_id),
                    )
                    ics_row = cur.fetchone()
                    has_ics_rows = int(_to_native(ics_row[0] if ics_row else 0) or 0) > 0
                    if not has_ics_rows:
                        allow_zero_c_id = True
                missing_class_key = (not c_id) and (not allow_zero_c_id)
                if missing_base_keys or missing_class_key:
                    raise UserError(_("Missing key values for return line update."))

                source_factor = float(line._get_source_factor())
                source_unit = int(line.source_itm_unit or 3)
                unit12 = float(line.item_unit1_unit2 or 1.0)
                unit13 = float(line.item_unit1_unit3 or 1.0)

                sell_source = float(line._price_to_source_unit(line.sell_price or 0.0))
                cost_source = float(line._price_to_source_unit(line.cost or 0.0))

                total_qty += q_back_source
                total_value += q_back_source * sell_source
                total_return_qty_source += q_back_source

                cur.execute(
                    f"""
                        SELECT ISNULL(SUM(itm_qty),0)
                        FROM item_class_store
                        WHERE itm_id = {PARAM_STR} AND sto_id = {PARAM_STR}
                    """,
                    (itm_id, sto_id),
                )
                stock_row = cur.fetchone()
                stock_small = float(stock_row[0] or 0.0) if stock_row else 0.0

                cur.execute(
                    f"""
                        UPDATE sales_trans_d
                           SET itm_back = ISNULL(itm_back, 0) + {PARAM_STR},
                               itm_unit = {PARAM_STR},
                               itm_back_price = {PARAM_STR},
                               itm_sell = {PARAM_STR},
                               itm_cost = {PARAM_STR},
                               itm_aver_cost = {PARAM_STR},
                               itm_back_tax = 0.0000,
                               itm_tax = 0.0000,
                               sec_update_uid = {PARAM_STR},
                               sec_update_date = GETDATE(),
                               std_r_itm_purchase_unit = 1,
                               std_r_itm_unit1_unit2 = {PARAM_STR},
                               std_r_itm_unit1_unit3 = {PARAM_STR},
                               std_r_itm_stock = {PARAM_STR},
                               itm_nexist = CASE
                                   WHEN ABS(ISNULL(qnty, 0) - (ISNULL(itm_back, 0) + {PARAM_STR})) <= 0.0001
                                       THEN 0
                                   ELSE itm_nexist
                               END
                         WHERE sth_id = {PARAM_STR}
                           AND itm_id = {PARAM_STR}
                           AND c_id = {PARAM_STR}
                           AND std_id = {PARAM_STR}
                    """,
                    (
                        q_back_source,
                        source_unit,
                        sell_source,
                        sell_source,
                        cost_source,
                        cost_source,
                        int(emp_id),
                        unit12,
                        unit13,
                        stock_small,
                        q_back_source,
                        int(sth_id),
                        itm_id,
                        c_id,
                        std_id,
                    ),
                )

                sold_source = float(line.qty_sold_source or 0.0)
                max_return_source = float(line.max_returnable_source or 0.0)
                existing_back_source = max(sold_source - max_return_source, 0.0)
                should_split = (
                        existing_back_source <= 1e-4
                        and q_back_source > 1e-4
                        and (sold_source - q_back_source) > 1e-4
                )

                if should_split:
                    remain_qty = sold_source - q_back_source
                    cur.execute(
                        f"SELECT ISNULL(MAX(std_id), 0) + 1 FROM sales_trans_d WHERE sth_id = {PARAM_STR}",
                        (int(sth_id),),
                    )
                    next_std_row = cur.fetchone()
                    next_std_id = int(next_std_row[0] or 1) if next_std_row else 1

                    cur.execute(
                        f"""
                            INSERT INTO sales_trans_d
                            (
                                std_id, sth_id, itm_id, c_id, exp_date,
                                qnty, itm_unit, itm_sell, itm_cost,
                                itm_dis_mon, itm_dis_per, itm_back,
                                itm_back_price, itm_aver_cost,
                                sec_insert_uid, sec_insert_date,
                                sec_update_uid, sec_update_date,
                                itm_nexist, std_itm_purchase_unit,
                                std_itm_unit1_unit2, std_itm_unit1_unit3, std_itm_stock
                            )
                            SELECT
                                {PARAM_STR}, sth_id, itm_id, c_id, exp_date,
                                {PARAM_STR}, itm_unit, itm_sell, itm_cost,
                                itm_dis_mon, itm_dis_per, 0,
                                itm_back_price, itm_aver_cost,
                                sec_insert_uid, sec_insert_date,
                                sec_update_uid, sec_update_date,
                                itm_nexist, 1,
                                {PARAM_STR}, {PARAM_STR}, {PARAM_STR}
                            FROM sales_trans_d
                            WHERE sth_id = {PARAM_STR}
                              AND itm_id = {PARAM_STR}
                              AND c_id = {PARAM_STR}
                              AND std_id = {PARAM_STR}
                        """,
                        (
                            next_std_id,
                            remain_qty,
                            unit12,
                            unit13,
                            stock_small,
                            int(sth_id),
                            itm_id,
                            c_id,
                            std_id,
                        ),
                    )

                    cur.execute(
                        f"""
                            UPDATE sales_trans_d
                               SET qnty = {PARAM_STR}
                             WHERE sth_id = {PARAM_STR}
                               AND itm_id = {PARAM_STR}
                               AND c_id = {PARAM_STR}
                               AND std_id = {PARAM_STR}
                        """,
                        (
                            q_back_source,
                            int(sth_id),
                            itm_id,
                            c_id,
                            std_id,
                        ),
                    )

                q_back_small = q_back_source * source_factor
                cur.execute(
                    f"""
                        UPDATE Item_Class_Store
                           SET itm_qty = itm_qty + {PARAM_STR},
                               sec_update_uid = {PARAM_STR},
                               sec_update_date = GETDATE()
                         WHERE itm_id = {PARAM_STR}
                           AND c_id = {PARAM_STR}
                           AND sto_id = {PARAM_STR}
                    """,
                    (
                        q_back_small,
                        int(emp_id),
                        itm_id,
                        c_id,
                        sto_id,
                    ),
                )

            if total_qty <= 0:
                raise UserError(_("Nothing to return."))

            cur.execute(
                f"""
                    INSERT INTO sales_return (
                        sth_id, returned_items_no, returned_items_value,
                        new_items_no, new_items_value,
                        sec_insert_uid, sth_extra_expenses_back, total_back_tax
                    )
                    VALUES ({PARAM_STR}, {PARAM_STR}, {PARAM_STR},
                            0, 0,
                            {PARAM_STR}, 0.0000, 0.0000)
                """,
                (
                    int(sth_id),
                    total_qty,
                    total_value,
                    int(emp_id),
                ),
            )

            sr_id = self._get_identity(cur, label="sales_return.sr_id")
            self.sales_return_id = sr_id

            net_return = total_value
            # if invoice is totally returned, then net_return = total_net_amount
            if abs(total_return_qty_source - total_sold_qty_source) < 0.01:
                # print(f"{self.total_sales_net=}\n{net_return=}")
                net_return = self.total_sales_net

            return_adjustments = self._get_return_adjustments(
                cur=cur,
                sth_id=sth_id,
                total_value=total_value,
                net_return=net_return,
            ) or {}
            total_bill_after_disc_delta = float(
                return_adjustments.get('total_bill_after_disc_delta', total_value) or 0.0
            )
            total_bill_net_delta = float(
                return_adjustments.get('total_bill_net_delta', net_return) or 0.0
            )
            fcs_current_balance_delta = float(
                return_adjustments.get('fcs_current_balance_delta', net_return) or 0.0
            )
            fh_value_delta = float(
                return_adjustments.get('fh_value_delta', fcs_current_balance_delta) or 0.0
            )
            sales_return_payment_value = float(
                return_adjustments.get('sales_return_payment_value', -fh_value_delta) or 0.0
            )

            cur.execute(
                f"""
                    UPDATE sales_trans_h
                       SET total_bill = total_bill - {PARAM_STR},
                           total_bill_after_disc = total_bill_after_disc - {PARAM_STR},
                           total_bill_net = total_bill_net - {PARAM_STR},
                           total_des_mon = total_des_mon - 0.00,
                           emp_id = {PARAM_STR},
                           sth_back = 1,
                           sec_update_uid = {PARAM_STR},
                           sec_update_date = GETDATE(),
                           sth_return_payment = 1
                     WHERE sth_id = {PARAM_STR}
                """,
                (
                    total_value,
                    total_bill_after_disc_delta,
                    total_bill_net_delta,
                    int(emp_id),
                    int(emp_id),
                    int(sth_id),
                ),
            )

            cur.execute(
                f"UPDATE sales_trans_h SET total_bill_net = 0 WHERE total_bill_net < 0 AND sth_id = {PARAM_STR}",
                (int(sth_id),),
            )
            cur.execute(
                f"UPDATE sales_trans_h SET total_bill_after_disc = 0 WHERE total_bill_after_disc < 0 AND sth_id = {PARAM_STR}",
                (int(sth_id),),
            )
            cur.execute(
                f"UPDATE sales_trans_h SET total_des_mon = 0 WHERE total_des_mon < 0 AND sth_id = {PARAM_STR}",
                (int(sth_id),),
            )
            cur.execute(
                f"UPDATE sales_trans_h SET sth_extra_expenses_back = 0.0000 WHERE sth_id = {PARAM_STR}",
                (int(sth_id),),
            )

            cur.execute(
                f"""
                    UPDATE F_Cash_Store
                       SET fcs_current_balance = fcs_current_balance - {PARAM_STR}
                     WHERE fcs_id = {PARAM_STR}
                """,
                (fcs_current_balance_delta, int(fcs_id)),
            )

            note = f" مرتجع بيع على فاتورة رقم {sth_id}"
            cur.execute(
                f"""
                    INSERT INTO F_Transaction_Header (
                        fh_trans_type, fh_trans_type2, fh_code,
                        fh_value, fh_From_type, fh_from_id,
                        fh_to_type, fh_to_id, fh_notes,
                        sec_insert_uid, fh_actual_date,
                        fh_computer, fh_actual_cashier_id,
                        fh_form_type, fh_sto_id, fh_cost_sto_id
                    )
                    VALUES (1, 2, '', {PARAM_STR},
                            '3', {PARAM_STR},
                            '1', 0, {PARAM_STR},
                            {PARAM_STR}, GETDATE(),
                            {PARAM_STR}, {PARAM_STR},
                            2, {PARAM_STR}, 0)
                """,
                (
                    fh_value_delta,
                    int(fcs_id),
                    note,
                    int(emp_id),
                    pc_name,
                    int(emp_id),
                    int(self.sto_eplus_serial or 0),
                ),
            )

            fh_id = self._get_identity(cur, label="F_Transaction_Header.fh_id")
            self.f_transaction_id = fh_id
            if fh_id:
                cur.execute(
                    f"UPDATE F_Transaction_Header SET fh_code = fh_id WHERE fh_id = {PARAM_STR}",
                    (int(fh_id),),
                )

            if sr_id:
                cur.execute(
                    f"""
                        INSERT INTO sales_return_payment (
                            srp_sto_id, srp_sr_id, srp_sr_type,
                            srp_pt_id, srp_fcs_id,
                            srp_value, srp_version,
                            srp_pc_name, srp_insert_uid
                        )
                        VALUES (
                            {PARAM_STR}, {PARAM_STR}, 2,
                            1, {PARAM_STR},
                            {PARAM_STR}, '13.0.86',
                            {PARAM_STR}, {PARAM_STR}
                        )
                    """,
                    (
                        int(self.sto_eplus_serial or 0),
                        int(sr_id),
                        int(fcs_id),
                        sales_return_payment_value,
                        pc_name,
                        int(emp_id),
                    ),
                )

            conn.commit()
            self.status = 'saved'

        except (UserError, ValidationError):
            try:
                conn.rollback()
            except Exception as e2:
                _logger.warning(repr(e2))
            raise
        except Exception as ex:
            try:
                conn.rollback()
            except Exception as e2:
                _logger.warning(repr(e2))
            raise UserError(_("E-Plus return push failed: %s") % str(ex))
        finally:
            pass

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
                raise UserError(_(
                    "Product '%s' is sold without balance.\nMust be returned completely!"
                ) % (line.product_id.display_name or ''))

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

    # ------------------ connection ------------------
    def get_connection(self):
        """Return real pyodbc connection, not context manager."""
        store_ip = self.store_id.ip1
        if self.store_id and not store_ip:
            raise UserError("No IP for this store")
        try:
            cm = self.connect_eplus(
                server=store_ip,
                autocommit=False,
                charset='UTF-8',
                param_str=PARAM_STR
            )
            conn = cm.__enter__()
            return conn

        except Exception as ex:
            if "Adaptive Server is unavailable or does not exist" in repr(ex):
                raise UserError(_("Server %s may be offline" % self.store_id.name))
            raise
