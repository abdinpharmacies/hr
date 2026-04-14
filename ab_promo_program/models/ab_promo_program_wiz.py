import re
from io import StringIO
import csv

from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import UserError


class AbPromoProgramWizard(models.TransientModel):
    _name = 'ab_promo_program_wizard'
    _description = 'Promo Program Excel Import Wizard'

    from_excel = fields.Text(
        string="Paste Excel Data",
        help=(
            "Copy rows from Excel and paste here (TAB-separated).\n"
            "First line MUST be headers.\n"
            "Use technical field names as headers, e.g.:\n"
            "name, max_repetition_per_invoice, rule_date_from, rule_date_to,\n"
            "rule_min_amount, rule_min_qty, disc_percent, apply_disc_on,\n"
            "fixed_price, product_code, disc_specific_product_ids\n\n"
            "- All headers are technical names EXCEPT 'product_code',\n"
            "  which is used to link to product_ids via ab_product.code.\n"
            "- 'disc_specific_product_ids' should contain product CODES\n"
            "  (comma-separated) that will be mapped to the Many2many field."
        ),
    )

    # -------------------------------------------------------------------------
    # Helper methods
    # -------------------------------------------------------------------------

    @staticmethod
    def _normalize_apply_disc_on(value):
        """Accept internal key or label; return valid selection key."""
        if not value:
            return False
        v = value.strip().lower()

        mapping = {
            'on_order': 'on_order',
            'on ordered quantity': 'on_order',
            'cheapest_product': 'cheapest_product',
            'on cheapest product': 'cheapest_product',
            'fixed_price': 'fixed_price',
            'fixed price': 'fixed_price',
            'specific_products': 'specific_products',
            'on specific products': 'specific_products',
        }
        res = mapping.get(v)
        if not res:
            raise UserError(_("Unknown value for 'apply_disc_on': %s") % value)
        return res

    @staticmethod
    def _float_or_false(value):
        value = (value or "").strip()
        if not value:
            return False
        try:
            return float(value.replace(',', ''))
        except Exception:
            raise UserError(_("Invalid float value: %s") % value)

    @staticmethod
    def _int_or_false(value):
        value = (value or "").strip()
        if not value:
            return False
        try:
            return int(float(value.replace(',', '')))
        except Exception:
            raise UserError(_("Invalid integer value: %s") % value)

    @staticmethod
    def _split_codes(value):
        """Split comma-separated product codes."""
        if not value:
            return []
        parts = [p.strip() for p in value.split(',')]
        return [p for p in parts if p]

    @staticmethod
    def _get_cell(row, header_map, header_name):
        """
        Get cell value by header technical name (case-insensitive).
        header_map: dict(header_name_lower -> index)
        """
        idx = header_map.get(header_name.lower())
        if idx is None or idx >= len(row):
            return ''
        return row[idx] or ''

    @staticmethod
    def _build_header_map(header_row):
        """
        Build {header_name_lower: index} and validate non-empty header row.
        """
        headers = [(c or '').strip() for c in header_row]
        if not headers or not any(headers):
            raise UserError(_("Header row is empty."))

        header_map = {h.lower(): idx for idx, h in enumerate(headers) if h}
        return header_map

    @staticmethod
    def _validate_required_headers(header_map, required_headers):
        missing_required = [h for h in required_headers if h.lower() not in header_map]
        if missing_required:
            raise UserError(
                _("Missing required header(s): %s") % ", ".join(missing_required)
            )

    @staticmethod
    def _derive_promo_fields(promo_text):
        """
        استنتاج:
        - rule_min_qty
        - disc_percent
        - apply_disc_on
        - fixed_price
        من promo_text فقط.

        أمثلة مدعومة:
        - '1+1'      -> Buy 2 get 1 free  (cheapest_product)
        - '2+1'      -> Buy 3 get 1 free  (cheapest_product)
        - '1+50%'    -> Buy 2, 50% on cheapest
        - '30%'      -> 30% on order
        - '190ج'     -> fixed price = 190
        """
        res = {
            'rule_min_qty': None,
            'disc_percent': None,
            'apply_disc_on': None,
            'fixed_price': None,
        }

        txt = (promo_text or '').strip()
        if not txt:
            return res

        # 1) نمط: 1+50%   (buy X, next واحد بخصم Y%)
        m = re.match(r'^\s*(\d+)\s*\+\s*(\d+)\s*%\s*$', txt)
        if m:
            buy_qty = int(m.group(1))
            perc = float(m.group(2))
            res['rule_min_qty'] = buy_qty + 1  # مثالك: 1+50% -> 2
            res['disc_percent'] = perc  # 50
            res['apply_disc_on'] = 'cheapest_product'
            res['fixed_price'] = 0.0
            return res

        # 2) نمط: 1+1 أو 2+1  (buy X get Y free على الأرخص)
        m = re.match(r'^\s*(\d+)\s*\+\s*(\d+)\s*$', txt)
        if m:
            x = int(m.group(1))
            y = int(m.group(2))
            res['rule_min_qty'] = x + y  # 1+1 -> 2, 2+1 -> 3
            res['disc_percent'] = 100.0
            res['apply_disc_on'] = 'cheapest_product'
            res['fixed_price'] = 0.0
            return res

        # 3) نمط: 30% أو 15%  (خصم عادي على الطلب)
        m = re.match(r'^\s*(\d+(\.\d+)?)\s*%\s*$', txt)
        if m:
            perc = float(m.group(1))
            res['rule_min_qty'] = 1
            res['disc_percent'] = perc
            res['apply_disc_on'] = 'on_order'
            res['fixed_price'] = 0.0
            return res

        # 4) نمط سعر ثابت: يبدأ برقم (190, 190ج, 190 LE, ...)
        m = re.match(r'^\s*(\d+(\.\d+)?)(.*)$', txt)
        if m:
            price = float(m.group(1))
            res['rule_min_qty'] = 1
            res['disc_percent'] = 0.0
            res['apply_disc_on'] = 'fixed_price'
            res['fixed_price'] = price
            return res

        # لو مش أي نمط معروف، رجع None وهنستخدم defaults
        return res

    # -------------------------------------------------------------------------
    # Main button
    # -------------------------------------------------------------------------
    def btn_add_promos(self):
        self.ensure_one()
        if not self.from_excel:
            raise UserError(_("Please paste Excel data first."))

        text = self.from_excel.strip()
        if not text:
            raise UserError(_("No data to import."))

        reader = csv.reader(StringIO(text), delimiter='\t')
        rows = list(reader)
        if not rows:
            raise UserError(_("No rows detected in pasted data."))

        # ---------------- HEADER ROW ----------------
        header_row = rows[0]
        header_map = self._build_header_map(header_row)

        # Required headers (technical names)
        # أول 5 أعمدة اللي هتدخلهم يدويًا
        self._validate_required_headers(
            header_map,
            ['name', 'product_code', 'promo_text', 'rule_date_from', 'rule_date_to']
        )

        promo_map = {}
        # promo_map[key] = {
        #   'vals': {...},
        #   'product_codes': set([...]),
        #   'disc_codes': set([...]),
        # }

        # ---------------- DATA ROWS ----------------
        for line_no, row in enumerate(rows[1:], start=2):  # line 2 = first data row
            if not row or not any((c or "").strip() for c in row):
                continue  # skip blank row

            name = (self._get_cell(row, header_map, 'name') or '').strip()
            if not name:
                raise UserError(_("Line %s: 'name' is required.") % line_no)

            product_code = (self._get_cell(row, header_map, 'product_code') or '').strip()
            if not product_code:
                raise UserError(_("Line %s: 'product_code' is required.") % line_no)

            promo_text = self._get_cell(row, header_map, 'promo_text')

            rule_date_from = (self._get_cell(row, header_map, 'rule_date_from') or '').strip() or False
            rule_date_to = (self._get_cell(row, header_map, 'rule_date_to') or '').strip() or False

            # الأعمدة الاختيارية – لو موجودة وتحتوي قيمة، يتم احترامها
            max_rep_str = self._get_cell(row, header_map, 'max_repetition_per_invoice') \
                if 'max_repetition_per_invoice' in header_map else ''
            rule_min_amount_str = self._get_cell(row, header_map, 'rule_min_amount') \
                if 'rule_min_amount' in header_map else ''
            rule_min_qty_str = self._get_cell(row, header_map, 'rule_min_qty') \
                if 'rule_min_qty' in header_map else ''
            disc_percent_str = self._get_cell(row, header_map, 'disc_percent') \
                if 'disc_percent' in header_map else ''
            apply_disc_on_raw = self._get_cell(row, header_map, 'apply_disc_on') \
                if 'apply_disc_on' in header_map else ''
            fixed_price_str = self._get_cell(row, header_map, 'fixed_price') \
                if 'fixed_price' in header_map else ''
            disc_codes_str = self._get_cell(row, header_map, 'disc_specific_product_ids') \
                if 'disc_specific_product_ids' in header_map else ''

            # --- اشتقاق القيم من promo_text ---
            derived = self._derive_promo_fields(promo_text)

            # rule_min_qty: أولوية للإكسيل، ثم المشتق، ثم 1 كـ default
            if rule_min_qty_str.strip():
                rule_min_qty = self._int_or_false(rule_min_qty_str) or 0
            else:
                rule_min_qty = derived['rule_min_qty'] if derived['rule_min_qty'] is not None else 1

            # disc_percent: أولوية للإكسيل، ثم المشتق، ثم 0
            if disc_percent_str.strip():
                disc_percent = self._float_or_false(disc_percent_str) or 0.0
            else:
                disc_percent = derived['disc_percent'] if derived['disc_percent'] is not None else 0.0

            # apply_disc_on: أولوية للإكسيل، ثم المشتق، ثم 'on_order'
            if apply_disc_on_raw.strip():
                apply_disc_on = self._normalize_apply_disc_on(apply_disc_on_raw)
            else:
                apply_disc_on = derived['apply_disc_on'] or 'on_order'

            # fixed_price: أولوية للإكسيل، ثم المشتق، ثم 0
            if fixed_price_str.strip():
                fixed_price = self._float_or_false(fixed_price_str) or 0.0
            else:
                fixed_price = derived['fixed_price'] if derived['fixed_price'] is not None else 0.0

            max_repetition_per_invoice = self._int_or_false(max_rep_str) if max_rep_str else False
            rule_min_amount = self._float_or_false(rule_min_amount_str) if rule_min_amount_str else False
            disc_codes = self._split_codes(disc_codes_str)

            # Grouping key (one promo per group)
            key = (
                name,
                rule_date_from or '',
                rule_date_to or '',
                rule_min_amount or 0.0,
                rule_min_qty,
                disc_percent,
                apply_disc_on,
                fixed_price,
                max_repetition_per_invoice or 0,
            )

            if key not in promo_map:
                promo_map[key] = {
                    'vals': {
                        'name': name,
                        'max_repetition_per_invoice': max_repetition_per_invoice or 3,
                        'rule_date_from': rule_date_from or False,
                        'rule_date_to': rule_date_to or False,
                        'rule_min_amount': rule_min_amount or 0.0,
                        'rule_min_qty': rule_min_qty,
                        'disc_percent': disc_percent,
                        'apply_disc_on': apply_disc_on,
                        'fixed_price': fixed_price,
                    },
                    'product_codes': set(),
                    'disc_codes': set(),
                }

            promo_map[key]['product_codes'].add(product_code)
            for c in disc_codes:
                promo_map[key]['disc_codes'].add(c)

        if not promo_map:
            raise UserError(_("No valid lines found to create promotions."))

        Product = self.env['ab_product'].with_context(active_test=False)
        Promo = self.env['ab_promo_program']

        created_promos = self.env['ab_promo_program']

        # Collect all codes
        all_product_codes = set()
        all_disc_codes = set()
        for data in promo_map.values():
            all_product_codes |= data['product_codes']
            all_disc_codes |= data['disc_codes']

        # Resolve product_code -> product_ids
        product_map = {}
        if all_product_codes:
            products = Product.search([('code', 'in', list(all_product_codes))])
            product_map = {p.code: p.id for p in products}
            missing = all_product_codes - set(product_map.keys())
            if missing:
                raise UserError(
                    _("The following product codes were not found (product_ids):\n%s")
                    % ', '.join(sorted(missing))
                )

        # Resolve disc_specific_product_ids (by code too)
        disc_map = {}
        if all_disc_codes:
            products_disc = Product.search([('code', 'in', list(all_disc_codes))])
            disc_map = {p.code: p.id for p in products_disc}
            missing_disc = all_disc_codes - set(disc_map.keys())
            if missing_disc:
                raise UserError(
                    _("The following product codes were not found (disc_specific_product_ids):\n%s")
                    % ', '.join(sorted(missing_disc))
                )

        # Create promos
        for key, data in promo_map.items():
            vals = data['vals'].copy()

            product_ids = [product_map[c] for c in data['product_codes']]
            disc_ids = [disc_map[c] for c in data['disc_codes']]

            if product_ids:
                vals['product_ids'] = [(6, 0, product_ids)]
            if disc_ids:
                vals['disc_specific_product_ids'] = [(6, 0, disc_ids)]

            promo = Promo.create(vals)
            created_promos |= promo
