# -*- coding: utf-8 -*-

from math import floor
from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval
from odoo.tools import float_round
import logging

_logger = logging.getLogger(__name__)


class AbSalesHeaderPromo(models.Model):
    _name = 'ab_sales_header'
    _inherit = ['ab_sales_header', 'abdin_et.extra_tools']

    def _program_is_effective(self, program):
        """
        If a promotion program has no configured products, treat it as inactive.
        - For 'specific_products': requires at least one discounted product.
        - For other types: requires explicit products or a products domain.
        - If program is restricted to stores, it must match header store_id.
        - If program is restricted to replica DBs, current db_serial must match.
        """
        self.ensure_one()
        if not program:
            return False
        if program.store_ids and (not self.store_id or self.store_id not in program.store_ids):
            return False
        if "replica_db_ids" in program._fields and program.replica_db_ids:
            replica_db = self.env["ab_replica_db"].sudo().get_current_from_config()
            if not replica_db or replica_db not in program.replica_db_ids:
                return False

        if program.apply_disc_on == 'specific_products':
            return bool(program.disc_specific_product_ids)

        return bool(program.product_ids) or bool((program.rule_products_domain or "").strip())

    def _compute_header_numbers(self, cur=None):
        """Keep sales_trans_h totals aligned with promotion discount during push."""
        totals = super()._compute_header_numbers(cur=cur)

        program = self.applied_program_ids.filtered(lambda p: self._program_is_effective(p))[:1]
        if not program:
            return totals

        # Ensure computed promo totals are current before pushing.
        try:
            self._compute_amounts()
            self._compute_promo_totals()
        except Exception:
            pass

        total_bill = float(totals.get("total_bill") or 0.0)
        promo_discount = float(self.promo_discount_amount or 0.0)
        if total_bill <= 0.0 or promo_discount <= 0.0:
            return totals

        promo_discount = min(promo_discount, total_bill)
        after = max(0.0, total_bill - promo_discount)
        totals["total_bill_net"] = self._to_2dec(after)
        return totals

    def _get_sales_trans_h_notice(self):
        self.ensure_one()
        description = super()._get_sales_trans_h_notice()
        if self.applied_program_ids.filtered(lambda p: self._program_is_effective(p)):
            description += '§§§'
        return description

    # Totals (untaxed math)
    currency_id = fields.Many2one('res.currency', default=lambda s: s.env.company.currency_id.id, required=True)
    amount_untaxed = fields.Monetary(compute='_compute_amounts', store=True)
    amount_tax = fields.Monetary(compute='_compute_amounts', store=True)
    amount_total = fields.Monetary(compute='_compute_amounts', store=True)

    # Attach programs *manually or via your own logic* (no validation layer here)
    applied_program_ids = fields.Many2many(
        comodel_name='ab_promo_program',
        relation='ab_sales_header_promo_program_validated_rel',
        column1='sales_header_id',
        column2='validated_promo_id',
        string="Applied Programs",
        copy=False,
    )

    available_program_ids = fields.Many2many(
        comodel_name='ab_promo_program',
        string="Available Programs",
        compute='_compute_available_program_ids'
    )
    promo_manual_override = fields.Boolean(default=False, copy=False)

    # Results
    promo_discount_amount = fields.Monetary(
        string="Promotion Discount",
        compute="_compute_promo_totals",
        store=True
    )
    amount_total_after_promo = fields.Monetary(
        string="Total After Promotion",
        compute="_compute_promo_totals",
        store=True
    )

    need_qty_to_unlock_promo = fields.Html(compute='_compute_need_qty_to_unlock_promo')

    @api.depends('available_program_ids')
    def _compute_need_qty_to_unlock_promo(self):
        for rec in self:
            msg = rec._next_promo_suggestion()
            if msg:
                rec.need_qty_to_unlock_promo = msg
            elif rec.available_program_ids and not rec.applied_program_ids:
                rec.need_qty_to_unlock_promo = """
                <div class='text-danger h3'>
                Choose manually from available promotions
                </div>
                """
            else:
                rec.need_qty_to_unlock_promo = ""

    # ---------------- Amounts (untaxed base) ---------------- #
    @api.depends('line_ids.price_subtotal', 'line_ids.price_tax')
    def _compute_amounts(self):
        for h in self:
            h.amount_untaxed = sum(h.line_ids.mapped('price_subtotal'))
            h.amount_tax = sum(h.line_ids.mapped('price_tax'))
            h.amount_total = h.amount_untaxed + h.amount_tax

    # ---------------- Final totals ---------------- #
    @api.depends(
        'amount_total',
        'applied_program_ids',
        'applied_program_ids.disc_percent',
        'applied_program_ids.apply_disc_on',
        'applied_program_ids.disc_specific_product_ids',
        'line_ids.product_id', 'line_ids.sell_price', 'line_ids.qty',
    )
    def _compute_promo_totals(self):
        for h in self:
            program = h.applied_program_ids.filtered(lambda p: h._program_is_effective(p))[:1]
            program_id = getattr(program, "id", None)
            origin = getattr(program_id, "origin", None)
            if origin:
                program = self.env["ab_promo_program"].browse(int(origin))
            products_in_order = h.line_ids.mapped('product_id')
            total_discount = 0.0
            if program:
                for prod in products_in_order:
                    total_discount += h._discount_for_program_on_product(program, prod) or 0.0

            h.promo_discount_amount = min(total_discount, h.amount_total)
            h.amount_total_after_promo = h.amount_total - h.promo_discount_amount

    # available programs -> use VISIBILITY scope
    @api.depends('line_ids.product_id', 'store_id')
    def _compute_available_program_ids(self):
        Promo = self.env['ab_promo_program'].sudo()
        now = fields.Datetime.now()
        for rec in self:
            products_in_order = rec.line_ids.mapped('product_id')
            if not products_in_order:
                rec.available_program_ids = [(6, 0, [])]
                continue

            domain = [
                ('active', '=', True),
                '|', ('company_id', '=', rec.company_id.id), ('company_id', '=', False),
                '|', ('rule_date_from', '=', False), ('rule_date_from', '<=', now),
                '|', ('rule_date_to', '=', False), ('rule_date_to', '>=', now),
            ]
            if rec.store_id:
                domain += ['|', ('store_ids', '=', False), ('store_ids', 'in', rec.store_id.id)]
            else:
                domain += [('store_ids', '=', False)]

            promos = Promo.search(domain, order='sequence,id')

            applicable = self.env['ab_promo_program']
            for p in promos:
                vis_scope = rec._program_visibility_products(p)
                if vis_scope & products_in_order and rec._program_is_effective(p):
                    applicable |= p

            rec.available_program_ids = [(6, 0, applicable.ids)]

    def btn_apply_promotion(self):
        for header in self:
            if header.status != 'prepending':
                continue
            header.promo_manual_override = False

            effective_applied = header.applied_program_ids.filtered(lambda p: header._program_is_effective(p))
            if effective_applied != header.applied_program_ids:
                header.applied_program_ids = [(6, 0, effective_applied.ids)]

            if not header.applied_program_ids:
                header._auto_apply_programs()
            header._apply_promotion_to_lines()
        return True

    def _recompute_promo_totals(self):
        self._compute_promo_totals()
        self.compute_totals()

    @api.onchange('applied_program_ids')
    def _onchange_applied_program_ids(self):
        for rec in self:
            if rec.status != 'prepending':
                continue
            prev_applied = rec._origin.applied_program_ids if rec._origin else rec.env['ab_promo_program']
            if rec.applied_program_ids:
                rec.promo_manual_override = False
            elif prev_applied:
                rec.promo_manual_override = True
            rec._recompute_promo_totals()

    @api.onchange('line_ids', 'store_id')
    def _onchange_auto_apply_single_promo(self):
        for rec in self:
            if rec.status != 'prepending':
                continue
            if rec.applied_program_ids:
                rec._recompute_promo_totals()
                continue
            if rec.promo_manual_override:
                rec._recompute_promo_totals()
                continue
            rec._compute_available_program_ids()
            if len(rec.available_program_ids) != 1:
                continue
            rec.applied_program_ids = [(6, 0, rec.available_program_ids.ids)]
            rec._recompute_promo_totals()

    @api.depends(
        'line_ids',
        'line_ids.qty',
        'line_ids.product_id',
        'amount_total_after_promo',
        'applied_program_ids',
        'promo_discount_amount',
    )
    def compute_totals(self):
        super().compute_totals()
        for header in self:
            if header.applied_program_ids:
                header.total_net_amount = header.amount_total_after_promo

    def _auto_apply_programs(self):
        """
        Auto-apply only if:
          - يوجد برنامج واحد متاح فقط
          - وإجمالي الكمية في نطاق خصم هذا البرنامج >= rule_min_qty (لو محددة)
        غير كده: لا يطبق أي برنامج أوتوماتيك.
        """
        for h in self:
            progs = h.available_program_ids.filtered(lambda p: h._program_is_effective(p))

            # لا أوتوماتيك لو مفيش أو أكتر من برنامج
            if len(progs) != 1:
                # ممكن تسيب القديم زي ما هو أو تفضي الحقل
                # h.applied_program_ids = [(6, 0, [])]
                continue

            program = progs[0]

            # نطاق المنتجات اللي يتطبق عليها الخصم فعلياً
            scope = h._program_discount_products(program)
            need_qty = float(program.rule_min_qty or 0.0)

            # احسب إجمالي الكمية في النطاق
            total_scope_qty = 0.0
            if scope:
                for line in h.line_ids:
                    if line.product_id in scope and (line.qty or 0.0) > 0:
                        total_scope_qty += h._line_qty_in_program_uom(line, program)

            # هل ينفع نطبق العرض أوتوماتيك؟
            # - لو مفيش نطاق: اعتبره دايماً متاح (أو غيّرها حسب اللوجيك عندك)
            # - لو rule_min_qty <= 0: مفيش حد أدنى
            if not scope or need_qty <= 0.0 or (total_scope_qty + 1e-8 >= need_qty):
                # ينفع نطبق البرنامج
                h.applied_program_ids = [(6, 0, [program.id])]
            else:
                # الكمية غير كافية → لا نطبق العرض أوتوماتيك
                h.applied_program_ids = [(6, 0, [])]

    @api.constrains('applied_program_ids', 'line_ids')
    def _constraint_ab_sales_header(self):
        for rec in self:
            def _get_code_with_padding(code):
                return code.ljust(6, '\u2007')

            if len(rec.applied_program_ids) > 1:
                raise ValidationError(_("Only one promotion per each invoice"))

            if rec.applied_program_ids:
                prog = rec.applied_program_ids
                prog_products = rec._program_discount_products(prog)
                prog_products_set = set(prog_products.ids)

                invoice_products_set = set(rec.line_ids.product_id.ids)
                out_prog_products_set = invoice_products_set - prog_products_set
                # if out_prog_products_set:
                #     out_prog_products = self.env['ab_product'].browse(list(out_prog_products_set))
                #     out_prod_msg = "\n".join(
                #         f"{_get_code_with_padding(prod.code)} || {prod.name}" for prod in out_prog_products)
                #     out_prod_msg += _("\n\nProducts out promotions!")
                #     raise ValidationError(out_prod_msg)

                total_promo_qty = sum(
                    rec._line_qty_in_program_uom(line, prog)
                    for line in rec.line_ids
                    if line.product_id.id in prog_products_set
                )
                max_repetition_per_invoice = prog.max_repetition_per_invoice
                rule_min_qty = prog.rule_min_qty
                max_promo_qty = max_repetition_per_invoice * rule_min_qty

                if total_promo_qty > max_promo_qty:
                    raise ValidationError(_("Invoice qty(%s) - must not exceed %s") % (total_promo_qty, max_promo_qty))

    def _product_lines(self, product):
        """All lines for a specific ab_product on this header."""
        self.ensure_one()
        return self.line_ids.filtered(lambda l: l.product_id == product)

    def _program_basis_uom(self, product, program):
        """Return the target product UoM used for promo quantity checks."""
        self.ensure_one()
        default_uom = product.uom_id
        if (program.promo_uom_basis or 'largest_uom') != 'smallest_uom':
            return default_uom
        category = getattr(default_uom, "category_id", False)
        category_uoms = category.uom_ids.filtered(lambda u: u.active) if category else self.env['ab_product_uom']
        if not category_uoms:
            return default_uom
        return category_uoms.sorted(lambda u: (float(u.factor or 0.0), u.id))[:1]

    def _line_qty_in_program_uom(self, line, program):
        """
        Convert a line quantity into the promo basis UoM.
        Largest-unit promos behave like box/carton promos by default, while
        smallest-unit promos let piece/sheet quantities unlock the offer.
        """
        product = line.product_id
        qty = float(line.qty or 0.0)
        if not product or qty <= 0.0:
            return 0.0

        default_uom = product.uom_id
        selected_uom = line.uom_id or default_uom
        target_uom = self._program_basis_uom(product, program) or default_uom

        sel_factor = float(getattr(selected_uom, "factor", 0.0) or 0.0)
        target_factor = float(getattr(target_uom, "factor", 0.0) or 0.0)

        if sel_factor <= 0.0 and target_factor > 0.0:
            sel_factor = target_factor
        if target_factor <= 0.0 and sel_factor > 0.0:
            target_factor = sel_factor
        if sel_factor <= 0.0:
            sel_factor = 1.0
        if target_factor <= 0.0:
            target_factor = 1.0

        ratio = sel_factor / target_factor
        if ratio <= 0.0:
            ratio = 1.0
        return qty * ratio

    def _line_qty_in_default_uom(self, line):
        """
        Convert a line quantity into the product default UoM (reference/big unit).
        Promotions should evaluate rule_min_qty using this normalized quantity.
        """
        product = line.product_id
        qty = float(line.qty or 0.0)
        if not product or qty <= 0.0:
            return 0.0

        default_uom = product.uom_id
        selected_uom = line.uom_id or default_uom

        sel_factor = float(getattr(selected_uom, "factor", 0.0) or 0.0)
        def_factor = float(getattr(default_uom, "factor", 0.0) or 0.0)

        if sel_factor <= 0.0 and def_factor > 0.0:
            sel_factor = def_factor
        if def_factor <= 0.0 and sel_factor > 0.0:
            def_factor = sel_factor
        if sel_factor <= 0.0:
            sel_factor = 1.0
        if def_factor <= 0.0:
            def_factor = 1.0

        ratio = sel_factor / def_factor
        if ratio <= 0.0:
            ratio = 1.0
        return qty * ratio

    def _price_in_program_uom(self, line, program):
        """Convert line sell price into the configured promo basis unit price."""
        self.ensure_one()
        product = line.product_id
        if not product:
            return 0.0

        default_uom = product.uom_id
        selected_uom = line.uom_id or default_uom
        target_uom = self._program_basis_uom(product, program) or default_uom

        sel_factor = float(getattr(selected_uom, "factor", 0.0) or 0.0)
        def_factor = float(getattr(default_uom, "factor", 0.0) or 0.0)
        target_factor = float(getattr(target_uom, "factor", 0.0) or 0.0)

        if sel_factor <= 0.0 and def_factor > 0.0:
            sel_factor = def_factor
        if def_factor <= 0.0 and sel_factor > 0.0:
            def_factor = sel_factor
        if target_factor <= 0.0 and def_factor > 0.0:
            target_factor = def_factor
        if sel_factor <= 0.0:
            sel_factor = 1.0
        if def_factor <= 0.0:
            def_factor = 1.0
        if target_factor <= 0.0:
            target_factor = 1.0

        ratio_to_default = sel_factor / def_factor
        if ratio_to_default <= 0.0:
            ratio_to_default = 1.0
        price_default = float(self._price_ref_from_line(line, ratio_to_default) or 0.0)
        return price_default * (target_factor / def_factor)

    def _subtotal_for_product(self, product):
        """Untaxed subtotal for this product (ignoring taxes)."""
        lines = self._product_lines(product)
        return sum((l.sell_price or 0.0) * (l.qty or 0.0) for l in lines)

    def _discount_for_program_on_product(self, program, product):
        """
        Compute discount contributed by `program` if we restrict its effect to `product` only.
        Ignores taxes. Supports:
          - on_order:        pct * subtotal(product)
          - specific_products: pct * subtotal(product) (only if product in specific list)
          - fixed_price:     if current unit price > fixed_price:
                                discount += (current_price - fixed_price) * qty
          - cheapest_product: pct * cheapest_unit(product), gated by qty >= need
        """

        self.ensure_one()
        pct = max(0.0, min(program.disc_percent or 0.0, 100.0)) / 100.0
        if pct <= 0.0 and program.apply_disc_on != 'fixed_price':
            # في fixed_price إحنا بنستخدم fixed_price مش disc_percent
            return 0.0

        scope = self._program_discount_products(program)
        if not scope or product not in scope:
            return 0.0

        # ------------------------------
        # 1) نسبة على إجمالي الطلب / أصناف محددة
        # ------------------------------
        if program.apply_disc_on in ('on_order', 'specific_products'):
            base = self._subtotal_for_product(product)
            return base * pct

        # ------------------------------
        # 2) Fixed-price case
        #    لو سعر الوحدة الحالي > fixed_price:
        #       discount += (current_price - fixed_price) * qty
        # ------------------------------
        if program.apply_disc_on == 'fixed_price':
            fp = float(program.fixed_price or 0.0)
            if fp <= 0.0:
                return 0.0  # مفيش سعر مستهدف ننزل له

            discount = 0.0

            # نعدّي على كل السطور لنفس الـ product في الطلب
            for line in self.line_ids:
                if line.product_id != product:
                    continue

                qty = float(line.qty or 0.0)
                if qty <= 0:
                    continue

                current_price = float(line.sell_price or 0.0)
                if current_price > fp:
                    # الخصم = فرق السعر لكل وحدة * الكمية
                    discount += (current_price - fp) * qty

            return discount

        # ------------------------------
        # 3) Buy-N get cheapest (cheapest_product)
        # ------------------------------
        if program.apply_disc_on == 'cheapest_product':
            # Generalized “Buy (N-1) get 1” based on sorted units:
            need = program.rule_min_qty
            if need < 1:
                need = 1

            units = self._scope_units(scope, program)  # [(price, prod)] sorted desc
            if not units:
                return 0.0

            pct = max(0.0, min(program.disc_percent or 0.0, 100000.0)) / 100.0
            if pct <= 0.0:
                return 0.0

            # free every N-th unit (1-based => idx % need == need-1 on 0-based)
            discount_for_this_product = 0.0
            for idx, (price, prod) in enumerate(units):
                if (idx + 1) % need == 0:  # 1-based N-th
                    if prod == product:
                        discount_for_this_product += price * pct

            return discount_for_this_product

        return 0.0

    # todo: fix multi call
    def _scope_units(self, products, program):
        """
        Return a list of (price, product) for each unit in scope,
        expanded by integer quantity in the promo basis UoM,
        sorted by price desc then product id.
        """
        self.ensure_one()
        units = []
        qty_by_product_price = {}
        qty_by_product = {}
        for l in self.line_ids.filtered(lambda x: x.product_id in products and (x.qty or 0) > 0):
            qty_program = self._line_qty_in_program_uom(l, program)
            if qty_program <= 0.0:
                continue
            price = float(self._price_in_program_uom(l, program) or 0.0)
            if price < 0:
                continue
            product = l.product_id
            product_id = product.id
            key = (product_id, price)
            qty_by_product_price[key] = {
                "qty": float((qty_by_product_price.get(key, {}).get("qty") or 0.0) + qty_program),
                "price": price,
                "product": product,
            }
            qty_by_product[product_id] = {
                "qty": float((qty_by_product.get(product_id, {}).get("qty") or 0.0) + qty_program),
                "value": float((qty_by_product.get(product_id, {}).get("value") or 0.0) + (qty_program * price)),
                "product": product,
            }

        # Primary expansion: aggregate fractional quantities by (product, unit price),
        # then take integer units. This avoids losing discount when quantities are split
        # across many lines (e.g., each line contributes < 1 default unit).
        for vals in qty_by_product_price.values():
            cnt = int(floor(float(vals["qty"] or 0.0) + 1e-8))
            if cnt <= 0:
                continue
            units.extend([(float(vals["price"] or 0.0), vals["product"])] * cnt)

        # Fallback: if all per-price buckets remained fractional, aggregate at product
        # level and use weighted average unit price instead of returning zero units.
        if not units and qty_by_product:
            for vals in qty_by_product.values():
                total_qty = float(vals.get("qty") or 0.0)
                cnt = int(floor(total_qty + 1e-8))
                if cnt <= 0:
                    continue
                avg_price = float(vals.get("value") or 0.0) / total_qty if total_qty > 0.0 else 0.0
                units.extend([(avg_price, vals["product"])] * cnt)

        # most expensive first; stable tiebreaker by product id
        units.sort(key=lambda t: (t[0], t[1].id), reverse=True)

        return units

    def _program_discount_products(self, program):
        Product = self.env['ab_product']
        if not self._program_is_effective(program):
            return Product.browse()
        if program.apply_disc_on == 'specific_products':
            return program.disc_specific_product_ids
        scope = program.product_ids
        if not scope and program.rule_products_domain:
            try:
                dom = safe_eval(program.rule_products_domain, {})
                scope = Product.search(dom)
            except Exception:
                scope = Product.browse()  # empty
        if scope:
            return scope
        return Product.browse()

    # --- NEW: visibility scope (used by available list) ---
    def _program_visibility_products(self, program):
        """Products that make this program appear as 'available'."""
        Product = self.env['ab_product']
        if not self._program_is_effective(program):
            return Product.browse()

        if program.apply_disc_on == 'specific_products':
            # Visibility is driven by trigger products (product_ids or domain),
            # not the discount target set.
            scope = program.product_ids
            if not scope and program.rule_products_domain:
                try:
                    dom = safe_eval(program.rule_products_domain, {})
                    scope = Product.search(dom)
                except Exception:
                    scope = Product.browse()
            if scope:
                return scope
            if program.disc_specific_product_ids:
                return program.disc_specific_product_ids
            return Product.browse()

        # For other types, visibility == discount scope
        return self._program_discount_products(program)

    def _apply_promotion_to_lines(self):
        self.ensure_one()

        lines = self.line_ids
        if not lines:
            return

        lines_missing_price = lines.filtered(lambda l: l.product_id and (l.sell_price or 0.0) <= 0.0)
        if lines_missing_price:
            lines_missing_price._compute_sell_price()

        program = self.applied_program_ids[:1]
        if not program or not self._program_is_effective(program):
            if program:
                self.applied_program_ids = [(6, 0, [])]
            return

        scope = self._program_discount_products(program)
        need_qty = float(program.rule_min_qty or 0.0)
        if need_qty > 0 and scope:
            total_scope_qty = sum(
                self._line_qty_in_program_uom(l, program)
                for l in lines
                if l.product_id in scope and (l.qty or 0.0) > 0
            )
            if total_scope_qty + 1e-8 < need_qty:
                raise ValidationError(_(
                    "Promotion '%s' requires at least %s unit(s) in the invoice scope."
                ) % (program.display_name, int(need_qty)))

        discounts_by_product_id = {}
        for product in lines.product_id:
            discounts_by_product_id[product.id] = float(
                self._discount_for_program_on_product(program, product) or 0.0
            )

        for product in lines.product_id:
            product_lines = lines.filtered(
                lambda l: l.product_id == product and (l.qty or 0.0) > 0 and (l.sell_price or 0.0) > 0.0
            )
            if not product_lines:
                continue

            product_discount_total = float(discounts_by_product_id.get(product.id, 0.0) or 0.0)
            if product_discount_total <= 0.0:
                continue

            subtotals = {l.id: float((l.qty or 0.0) * (l.sell_price or 0.0)) for l in product_lines}
            product_subtotal = sum(subtotals.values())
            if product_subtotal <= 0.0:
                continue

            product_discount_total = min(product_discount_total, product_subtotal)

            remaining = product_discount_total
            line_ids = product_lines.ids
            for idx, line in enumerate(product_lines):
                line_subtotal = subtotals.get(line.id, 0.0)
                if idx == len(line_ids) - 1:
                    line_discount_total = remaining
                else:
                    ratio = (line_subtotal / product_subtotal) if product_subtotal else 0.0
                    line_discount_total = float_round(product_discount_total * ratio, precision_digits=2)
                    remaining -= line_discount_total

                qty = float(line.qty or 0.0)
                if qty <= 0.0:
                    continue

    def _next_promo_suggestion(self):
        """
        Build human-readable warnings for available promotions:
          - If chunk is incomplete: show how many units are needed to unlock.
          - If apply_disc_on == 'specific_products' and discounted products aren't in the order:
            show a warning listing the missing discounted SKUs.
        Returns HTML (or "").
        """
        self.ensure_one()

        messages = []

        # Current products in order
        products_in_order = self.line_ids.mapped('product_id')

        for program in self.applied_program_ids.filtered(lambda p: self._program_is_effective(p)):
            # 1) Missing-quantity warning (based on DISCOUNT scope)
            disc_scope = self._program_discount_products(program)
            if disc_scope:
                need = int(program.rule_min_qty or 0)
                if need > 0:
                    units = self._scope_units(disc_scope, program)  # expanded & sorted units in discount scope
                    r = len(units) % need
                    missing = (need - r) % need  # 0 if already aligned
                    if missing:
                        messages.append(
                            _(
                                "Customer needs <b>%s</b> more unit(s) to unlock promotion <b>%s</b>.",
                                missing, program.display_name
                            )
                        )

            # 2) Discounted-products presence warning (only for specific_products)
            if program.apply_disc_on == 'specific_products':
                # Visibility is triggered by product_ids or domain (handled elsewhere).
                # Discount, however, applies on disc_specific_product_ids:
                discounted = program.disc_specific_product_ids
                if discounted:
                    # Are any discounted SKUs present?
                    if not (discounted & products_in_order):
                        # Show a concise list (first few names); avoid huge messages
                        names = discounted.mapped('display_name')[:5]
                        more = ''
                        if len(discounted) > 5:
                            more = _(" and %s more...", len(discounted) - 5)
                        messages.append(
                            _(
                                "To apply promotion <b>%s</b>, add any discounted product: <i>%s</i>%s",
                                program.display_name,
                                ", ".join(names),
                                more
                            )
                        )

        if not messages:
            return ""

        # Wrap in a red-ish block like you had
        return """
            <div class="text-danger">
                <ul>{items}</ul>
            </div>
        """.format(items="".join(f"<li>{m}</li>" for m in messages))

    def btn_show_balance_for_all_stores(self):
        product_serials = self.line_ids.product_id.mapped('eplus_serial')
        if not product_serials:
            return self.ab_msg(title="Store Balances", message="No products on the invoice.")
        html = self.env['ab_product']._get_all_stores_balance_html(product_serials)

        return self.ab_msg(title="Store Balances", message=html)
