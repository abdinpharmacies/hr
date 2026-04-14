import logging
import math
import re
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

import json

from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import config

PARAM_STR = '?'

_logger = logging.getLogger(__name__)

DB_SERIAL = int(config.get('db_serial', 0)) * 1000_000_000


def _is_int_units(x, tol_units=0.001):
    # tol in **small units**, not big units
    return abs(x - round(x)) <= tol_units


def _int_floor_units(x):
    # safest integer not exceeding x
    return int(math.floor(float(x) + 1e-6))


def _safe_date_to_str(dt_str):
    if not dt_str:
        return None
    try:
        try:
            dt = datetime.strptime(dt_str[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            dt = datetime.fromisoformat(dt_str.replace("Z", ""))
        return dt.strftime("%Y/%m/%d")
    except Exception:
        return None


def _parse_dt_to_key(dt_str):
    # returns sortable key; invalid/empty -> far future
    try:
        return datetime.strptime((dt_str or "")[:19], "%Y-%m-%d %H:%M:%S")
    except Exception:
        return datetime.max


# ======================= JSON helpers (line.inventory_json = dict) ======================= #

def _parse_inventory_json(line):
    """
    يقرأ line.inventory_json كـ dict من نوع:
        {"data": [ {...}, {...}, ... ]}
    ويرجع list من السطور الصالحة مع qty > 0.
    """
    payload = getattr(line, "inventory_json", None) or {}
    if not isinstance(payload, dict):
        return []

    rows = payload.get("data") or []
    out = []
    for r in rows:
        try:
            q = float(r.get("qty", 0) or 0)
            q_small = float(r.get("qty_in_small_unit", 0) or 0)
            if q <= 0 and q_small <= 0:
                continue
            out.append({
                "source_id": r.get("source_id"),
                "exp_date": r.get("exp_date"),
                "qty": q,
                "qty_in_small_unit": q_small,
                "product_eplus_serial": r.get("product_eplus_serial"),
                "store_eplus_serial": r.get("store_eplus_serial"),
                "price": r.get("price"),
                "cost": r.get("cost"),
            })
        except Exception:
            continue
    return out


def _eq_price_2dec(a, b):
    # compare to 2 decimals to avoid float noise
    try:
        return round(float(a or 0), 2) == round(float(b or 0), 2)
    except Exception:
        return False


def _fifo_batches_for_line(
        qty_small,
        product_eplus_serial,
        sell_price,
        all_rows,
        store_eplus=None,
        allow_fraction=True,
        product_name=None,
):
    """
    FIFO chunks for this line as:
        (source_id, exp_date_str, qty_to_take, sell_price, batch_cost, is_missing)

    qty_small is in small units, and inventory rows are consumed using qty_in_small_unit.
    """
    need = float(qty_small or 0)
    # POS: always allow fractional quantities
    if need <= 0:
        return

    all_rows = all_rows or []

    prod_serial = int(product_eplus_serial or 0)
    if prod_serial:
        all_rows = [
            r for r in all_rows
            if int(r.get("product_eplus_serial") or 0) == prod_serial
        ]

    if store_eplus:
        try:
            se = int(store_eplus)
            all_rows = [
                r for r in all_rows
                if int(r.get("store_eplus_serial") or 0) == se
            ]
        except Exception:
            pass

    rows = []
    for r in all_rows:
        try:
            q_small = float(r.get("qty_in_small_unit") or 0)
            if not allow_fraction:
                q_small = _int_floor_units(q_small)
            if q_small <= 0:
                continue
            rows.append({
                "source_id": r.get("source_id"),
                "exp_date": r.get("exp_date"),
                "qty_small": q_small,
                "price": r.get("price"),
                "cost": r.get("cost"),
            })
        except Exception:
            continue

    if not rows:
        if need > 1e-4:
            yield (
                0,
                None,
                float(need),
                float(sell_price or 0),
                float((sell_price or 0) * 0.85),
                1,
            )
        return

    target_price = float(sell_price or 0)

    same_price_rows = [
        r for r in rows
        if r.get("price") is not None and _eq_price_2dec(r["price"], target_price)
    ]

    def fifo_key(r):
        exp = r.get("exp_date")
        try:
            ts = datetime.strptime((exp or "")[:19], "%Y-%m-%d %H:%M:%S")
        except Exception:
            ts = datetime.max
        sid = int(r.get("source_id") or 0)
        return ts, sid

    same_price_rows.sort(key=fifo_key)

    remaining = float(need)

    for r in same_price_rows:
        if remaining <= 0:
            break
        row_qty = float(r.get("qty_small") or 0)
        if row_qty <= 0:
            continue

        take = row_qty if row_qty <= remaining else remaining
        batch_price = float(r.get("price") or 0)
        batch_cost = float(r.get("cost") or 0)

        yield (
            int(r.get("source_id") or 0),
            _safe_date_to_str(r.get("exp_date")),
            float(take),
            float(batch_price),
            float(batch_cost),
            0,
        )
        remaining -= take

    if remaining <= 1e-4:
        return

    other_rows = [
        r for r in rows
        if not (r.get("price") is not None and _eq_price_2dec(r["price"], target_price))
    ]

    def other_key(r):
        price = r.get("price")
        try:
            p = float(price)
        except (TypeError, ValueError):
            p = float('inf')

        exp = r.get("exp_date")
        try:
            ts = datetime.strptime((exp or "")[:19], "%Y-%m-%d %H:%M:%S")
        except Exception:
            ts = datetime.max

        sid = int(r.get("source_id") or 0)
        return p, ts, sid

    other_rows.sort(key=other_key)

    for r in other_rows:
        if remaining <= 0:
            break
        row_qty = float(r.get("qty_small") or 0)
        if row_qty <= 0:
            continue

        take = row_qty if row_qty <= remaining else remaining
        batch_cost = float(r.get("cost") or 0)

        yield (
            int(r.get("source_id") or 0),
            _safe_date_to_str(r.get("exp_date")),
            float(take),
            float(target_price),
            float(batch_cost),
            0,
        )
        remaining -= take

    if remaining > 1e-4:
        yield (
            0,
            None,
            float(remaining),
            float(sell_price or 0),
            float((sell_price or 0) * 0.85),
            1,
        )


def _factor_from_inventory_json(line):
    """
    يحسب معامل التحويل (الصغرى/الكبرى) من أول عنصر صالح في inventory_json (dict).
    لو مش متاح يرجّع None.
    """
    payload = getattr(line, "inventory_json", None) or {}
    if not isinstance(payload, dict):
        return None

    rows = payload.get('data', []) or []
    for r in rows:
        try:
            q_big = float(r.get('qty') or 0)
            q_small = float(r.get('qty_in_small_unit') or 0)
            if q_big > 0 and q_small > 0:
                return q_small / q_big
        except Exception:
            continue
    return None


# ======================= Model: AbdinSalesHeader ======================= #

class AbdinSalesHeader(models.Model):
    _name = 'ab_sales_header'
    _description = 'ab_sales_header'
    _rec_name = 'id'
    _order = 'id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'ab_eplus_connect']

    repl_db = int(config.get('repl_db', 0)) or False

    store_id = fields.Many2one(
        'ab_store', required=True,
        domain=lambda self: self._get_allowed_store_domain(),
        default=lambda self: self._default_sales_store_id(),
    )
    store_ip = fields.Char(related='store_id.ip1')
    store_code = fields.Char(related='store_id.code', string='Store Code')
    store_server_online = fields.Boolean(compute='_compute_store_server_online')
    company_id = fields.Many2one(
        'res.company', string='Company',
        index=True, default=lambda self: self.env.company
    )
    customer_id = fields.Many2one('ab_customer')
    invoice_address = fields.Char()
    customer_address = fields.Char(related='customer_id.address', string="Address")
    customer_mobile = fields.Char(related='customer_id.mobile_phone', string="Mobile")
    customer_phone = fields.Char(related='customer_id.work_phone', string="Phone")
    customer_code = fields.Char(related='customer_id.code', string="Code")

    is_delivery = fields.Boolean()
    number_of_products = fields.Integer(compute='compute_totals', compute_sudo=True, )
    total_price = fields.Float(compute='compute_totals', compute_sudo=True, )
    total_net_amount = fields.Float(compute='compute_totals', compute_sudo=True, )
    description = fields.Text()
    status = fields.Selection(
        selection=[('prepending', 'PrePending'),
                   ('pending', 'Pending'),
                   ('saved', 'Saved')],
        default='prepending'
    )
    is_closed = fields.Boolean()

    line_ids = fields.One2many(
        comodel_name='ab_sales_line',
        inverse_name='header_id',
        string='Details',
    )

    invoice_address_datalist = fields.Char(compute='_compute_invoice_address_datalist', compute_sudo=True, )
    eplus_serial = fields.Integer(readonly=True, copy=False, string="ePlus Serial")
    push_state = fields.Selection(
        [('none', 'None'), ('success', 'Success'), ('error', 'Error')],
        default='none', readonly=True, copy=False
    )
    push_message = fields.Text(readonly=True, copy=False)

    new_customer_name = fields.Char()
    new_customer_phone = fields.Char()
    new_customer_address = fields.Char()
    bill_customer_name = fields.Char()
    bill_customer_phone = fields.Char(index=True)
    bill_customer_address = fields.Char()
    customer_insurance_name = fields.Char()
    customer_insurance_number = fields.Char()
    pos_client_token = fields.Char(index=True)
    employee_id = fields.Many2one(
        "ab_hr_employee",
        string="ePlus Employee",
        domain=lambda self: [
            "|",
            ("user_id", "=", self.env.user.id),
            "&",
            ("user_id", "!=", False),
            ("costcenter_id.eplus_serial", "!=", False),
        ],
        default=lambda self: self._default_employee_id(),
    )

    notice_header_ids = fields.Many2many(
        'ab_sales_return_header',
        compute='_compute_notice_header_ids',
        string="Returns",
        readonly=True,
        compute_sudo=True,
    )
    active = fields.Boolean(default=True)

    @api.model
    def _get_allowed_store_ids(self):
        replica_db = self.env["ab_replica_db"].sudo().get_current_from_config()
        if not replica_db:
            return []
        stores = replica_db.allowed_sales_store_ids.filtered("allow_sale")
        return stores.ids

    @api.model
    def _get_default_store_id(self):
        replica_db = self.env["ab_replica_db"].sudo().get_current_from_config()
        if not replica_db:
            return False
        store = replica_db.default_sales_store_id
        return store.id if store and store.allow_sale else False

    @api.model
    def _get_allowed_store_domain(self):
        domain = [("allow_sale", "=", True)]
        store_ids = self._get_allowed_store_ids()
        if store_ids:
            domain.append(("id", "in", store_ids))
        return domain

    @api.model
    def _default_sales_store_id(self):
        default_store_id = self._get_default_store_id()
        return default_store_id

    @api.constrains("store_id")
    def _check_store_allowed(self):
        store_ids = self._get_allowed_store_ids()
        if not store_ids:
            return
        for rec in self:
            if rec.store_id and rec.store_id.id not in store_ids:
                raise UserError(_("Store %s is not allowed for sales.") % (rec.store_id.display_name,))

    _uniq_pos_client_token = models.Constraint(
        "UNIQUE(pos_client_token)",
        _("POS submit token must be unique."),
    )

    def _compute_notice_header_ids(self):
        self = self.sudo()
        ReturnHeader = self.env['ab_sales_return_header']
        for rec in self:
            if not rec.eplus_serial:
                rec.notice_header_ids = ReturnHeader.browse()
                continue
            rec.notice_header_ids = ReturnHeader.search(
                [('origin_header_id', '=', int(rec.eplus_serial))],
                order='id desc',
            )

    @api.model
    def _sanitize_id_domain(self, domain):
        if not domain:
            return domain

        sanitized = []
        for token in domain:
            if token in ("|", "&", "!"):
                sanitized.append(token)
                continue

            if isinstance(token, (list, tuple)) and len(token) >= 3:
                field_name, op, value = token[0], token[1], token[2]
                if field_name == "id":
                    if op in ("in", "not in"):
                        if isinstance(value, (list, tuple, set)):
                            values = value
                        else:
                            values = [value]
                        ids = []
                        for v in values:
                            try:
                                ids.append(int(v))
                            except Exception:
                                continue
                        if ids:
                            sanitized.append((field_name, op, ids))
                        else:
                            sanitized.append(("id", "!=", 0) if op == "not in" else ("id", "=", 0))
                        continue
                    if op == "=":
                        try:
                            sanitized.append((field_name, op, int(value)))
                        except Exception:
                            sanitized.append(("id", "=", 0))
                        continue
                    if op == "!=":
                        try:
                            sanitized.append((field_name, op, int(value)))
                        except Exception:
                            sanitized.append(("id", "!=", 0))
                        continue

                sanitized.append(token)
                continue

            sanitized.append(token)
        return sanitized

    @api.model
    def _search(
            self,
            domain,
            offset=0,
            limit=None,
            order=None,
            *,
            active_test=True,
            bypass_access=False,
    ):
        # Guard against virtual/invalid ids (e.g. "1v") injected by the client.
        domain = self._sanitize_id_domain(domain)
        return super()._search(
            domain,
            offset=offset,
            limit=limit,
            order=order,
            active_test=active_test,
            bypass_access=bypass_access,
        )

    def action_open_add_products(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "ab_sales.add_products",
            "name": _("Add Products"),
            "target": "new",
            "context": dict(
                self.env.context,
                active_id=self.id,
                active_ids=[self.id],
                dialog_size="large",
                pos_store_id=self.store_id.id if self.store_id else False,
                pos_store_name=self.store_id.display_name if self.store_id else "",
            ),
        }

    def action_open_form_dialog(self):
        self.ensure_one()
        view_id = self.env.ref("ab_sales.ab_sales_header_view_form", raise_if_not_found=False)
        return {
            "type": "ir.actions.act_window",
            "name": _("Sales Header"),
            "res_model": "ab_sales_header",
            "res_id": self.id,
            "view_mode": "form",
            "views": [[view_id.id if view_id else False, "form"]],
            "target": "new",
        }

    def action_open_sales_return(self):
        self.ensure_one()
        if not self.store_id:
            raise UserError(_("Please select a Store first."))
        if not self.eplus_serial:
            raise UserError(_("Please Submit this invoice first."))

        ReturnHeader = self.env['ab_sales_return_header']
        return_header = ReturnHeader.search([
            ('origin_header_id', '=', int(self.eplus_serial)),
            ('store_id', '=', self.store_id.id),
            ('status', '=', 'prepending'),
        ], order='id desc', limit=1)
        if not return_header:
            return_header = ReturnHeader.create({
                'store_id': self.store_id.id,
                'origin_header_id': int(self.eplus_serial),
            })
        return return_header.with_context(curr_target='new').action_load_lines()

    # --------------------- New customer validation --------------------- #
    def _validate_new_customer(self):
        rec = self
        flds = [rec.new_customer_name, rec.new_customer_phone, rec.new_customer_address]

        if any(flds):
            if not all(flds):
                raise UserError(_("All 'New Customer' fields must set!"))

            # Name
            if rec.new_customer_name:
                words = rec.new_customer_name.strip().split()
                if len(words) < 2 and any(len(w) < 2 for w in words):
                    raise ValidationError(
                        "Name must contain at least two words, each with at least 2 characters."
                    )
            else:
                raise ValidationError("Name is required.")

            # Mobile
            if rec.new_customer_phone:
                if not re.fullmatch(r'01[0125]\d{8}', rec.new_customer_phone):
                    raise ValidationError(
                        "Mobile number must be 11 digits and start with 010, 011, 012, or 015."
                    )
            else:
                raise ValidationError("Mobile phone is required.")

            # Address
            if rec.new_customer_address:
                if len(rec.new_customer_address.strip()) < 2:
                    raise ValidationError("Address must be at least 2 characters long.")
            else:
                raise ValidationError("Address is required.")
            return True
        return False

    def _get_bill_customer_snapshot_vals(self):
        self.ensure_one()
        name = (self.bill_customer_name or "").strip()
        phone = (self.bill_customer_phone or "").strip()
        address = (self.bill_customer_address or "").strip()

        has_new = any([
            self.new_customer_name,
            self.new_customer_phone,
            self.new_customer_address,
        ])

        if not (name or phone or address):
            if has_new:
                name = (self.new_customer_name or "").strip()
                phone = (self.new_customer_phone or "").strip()
                address = (self.new_customer_address or "").strip()
            else:
                cust = self.customer_id
                name = (cust.name or "").strip() if cust else ""
                phone = ""
                if cust:
                    phone = (cust.work_phone or "").strip() or (cust.mobile_phone or "").strip() or (
                            cust.delivery_phone or "").strip()
                address = (self.invoice_address or "").strip()
                if not address and cust:
                    address = (cust.address or "").strip()
        else:
            if has_new:
                if not name:
                    name = (self.new_customer_name or "").strip()
                if not phone:
                    phone = (self.new_customer_phone or "").strip()
                if not address:
                    address = (self.new_customer_address or "").strip()
            else:
                cust = self.customer_id
                if not name and cust:
                    name = (cust.name or "").strip()
                if not phone and cust:
                    phone = (cust.work_phone or "").strip() or (cust.mobile_phone or "").strip() or (
                            cust.delivery_phone or "").strip()
                if not address:
                    address = (self.invoice_address or "").strip()
                    if not address and cust:
                        address = (cust.address or "").strip()
        return {
            "bill_customer_name": name,
            "bill_customer_phone": phone,
            "bill_customer_address": address,
        }

    @api.model
    def action_fix_bill_customer_data(self, domain=None, limit=None):
        Header = self.env["ab_sales_header"].sudo()
        target_ids = None
        if self:
            target_ids = self.sudo().ids
        elif domain or limit:
            target_ids = Header.search(domain or [], limit=limit).ids

        if target_ids is not None and not target_ids:
            return {
                "processed": 0,
                "filled_from_customer": 0,
                "relinked_customer": 0,
            }

        scope_clause = ""
        scope_params = []
        if target_ids is not None:
            scope_clause = " AND h.id = ANY(%s)"
            scope_params.append(target_ids)

        if target_ids is None:
            self.env.cr.execute("SELECT COUNT(*) FROM ab_sales_header")
            processed = int((self.env.cr.fetchone() or [0])[0] or 0)
        else:
            self.env.cr.execute("SELECT COUNT(*) FROM ab_sales_header WHERE id = ANY(%s)", (target_ids,))
            processed = int((self.env.cr.fetchone() or [0])[0] or 0)

        # Fill bill customer snapshot fields from linked customer only.
        # Keep existing bill values; only fill empty fields.
        self.env.cr.execute(
            f"""
            UPDATE ab_sales_header h
               SET bill_customer_name = CASE
                                            WHEN COALESCE(h.bill_customer_name, '') = '' THEN COALESCE(c.name, '')
                                            ELSE h.bill_customer_name
                                        END,
                   bill_customer_phone = CASE
                                             WHEN COALESCE(h.bill_customer_phone, '') = '' THEN COALESCE(c.mobile_phone, '')
                                             ELSE h.bill_customer_phone
                                         END,
                   bill_customer_address = CASE
                                               WHEN COALESCE(h.bill_customer_address, '') = '' THEN COALESCE(c.address, '')
                                               ELSE h.bill_customer_address
                                           END
              FROM ab_customer c
             WHERE h.customer_id = c.id
               AND (
                   COALESCE(h.bill_customer_name, '') = ''
                   OR COALESCE(h.bill_customer_phone, '') = ''
                   OR COALESCE(h.bill_customer_address, '') = ''
               )
               {scope_clause}
            """,
            tuple(scope_params),
        )

        self.env.cr.execute("""UPDATE
                                   ab_sales_header
                               set bill_customer_name=new_customer_name,
                                   bill_customer_phone = new_customer_phone,
                                   bill_customer_address = new_customer_address
                               where new_customer_phone like '01%'
                            """)
        return True

    @api.model
    def _to_2dec(self, val):
        return float(Decimal(val or 0).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

    @api.model
    def _default_employee_id(self):
        Employee = self.env["ab_hr_employee"].sudo()
        employee = Employee.search(
            [
                ("user_id", "=", self.env.user.id),
            ],
            limit=1,
        )
        return employee.id or False

    @api.model
    def _get_eplus_emp_id(self, employee=False):
        eplus_emp_id = 0
        Employee = self.env["ab_hr_employee"].sudo()
        if employee:
            if hasattr(employee, "ids"):
                employee = employee.sudo().exists()[:1]
            else:
                try:
                    employee = Employee.browse(int(employee)).exists()
                except Exception:
                    employee = Employee.browse()
        else:
            employee = Employee.search([("user_id", "=", self.env.user.id)], limit=1)
        if employee:
            eplus_emp_id = employee.costcenter_id.eplus_serial if employee.costcenter_id else 0
        if employee and not eplus_emp_id:
            emp_code = employee.costcenter_id.code if employee.costcenter_id else False
            if emp_code:
                conn = self.get_connection()
                with conn.cursor() as crx:
                    crx.execute(f"select e_id from employee where e_code = {PARAM_STR}", (emp_code,))
                    data = crx.fetchone()
                    eplus_emp_id = data and int(data[0]) or 0
                    if eplus_emp_id:
                        employee.with_context(replication=True).sudo().costcenter_id.eplus_serial = eplus_emp_id
        return eplus_emp_id

    def _get_pc_name(self):
        return self.env.user.login or 'ODOO'

    @staticmethod
    def _decode_arabic_mojibake(text):
        if not text:
            return text
        if any('\u0600' <= ch <= '\u06ff' for ch in text):
            return text
        try:
            candidate = text.encode("latin-1", errors="ignore").decode("cp1256", errors="ignore")
            if any('\u0600' <= ch <= '\u06ff' for ch in candidate):
                return candidate
        except Exception:
            pass
        return text

    def _format_eplus_error(self, ex):
        raw = ""
        try:
            if getattr(ex, "args", None):
                raw = " ".join([str(a) for a in ex.args if a is not None])
        except Exception:
            raw = ""
        if not raw:
            raw = str(ex)
        if not raw:
            raw = repr(ex)
        return self._decode_arabic_mojibake(raw)

    def _get_line_uom_context(self, cur, line):
        item_factor = self._get_item_catalog_factor(cur, line.product_id.eplus_serial)
        uom_factor = line.uom_id.factor if line.uom_id and line.uom_id.factor else item_factor
        if not item_factor:
            item_factor = uom_factor or 1.0
        if not uom_factor:
            uom_factor = item_factor or 1.0
        ratio = float(uom_factor) / float(item_factor or 1.0)
        if ratio <= 0:
            ratio = 1.0
        return float(item_factor), float(uom_factor), float(ratio)

    def _price_ref_from_line(self, line, ratio):
        """
        Convert line.sell_price to reference-unit price when it looks like a
        per-selected-UoM price; otherwise keep it as reference price.
        """
        price = float(line.sell_price or 0.0)
        if not ratio or abs(ratio - 1.0) <= 1e-6:
            return price
        default_price = float(line.product_id.default_price or 0.0)
        expected_selected = default_price * float(ratio)
        if expected_selected and price <= (expected_selected * 1.2 + 0.01):
            return price / float(ratio or 1.0)
        return price

    def _compute_header_numbers(self, cur=None):
        """Compute sales_trans_h totals, honoring UoM conversion when possible."""
        total_bill = 0.0
        total_net = 0.0
        for line in self.line_ids:
            line_total = float(line.qty or 0.0) * float(line.sell_price or 0.0)
            if cur and line.product_id:
                _item_factor, _uom_factor, ratio = self._get_line_uom_context(cur, line)
                price_ref = self._price_ref_from_line(line, ratio)
                price_selected = price_ref * ratio
                line_total = float(line.qty or 0.0) * float(price_selected or 0.0)
            total_bill += line_total
            total_net += line_total
        return {
            'no_of_items': len(self.line_ids),
            'total_bill': self._to_2dec(total_bill),
            'total_bill_after_disc': self._to_2dec(total_bill),
            'total_bill_net': self._to_2dec(total_net),
            'total_dis_per': 0,
            'total_des_mon': 0,
            'total_tax': 0.0,
        }

    def _validate_before_push(self):
        if self.status != 'prepending':
            raise UserError(_("Invoice must be in prepending status"))
        if not self.store_id or not self.store_id.eplus_serial:
            raise UserError(_("Store is required and must have an E-Plus serial."))
        if not self.line_ids:
            raise UserError(_("No lines to send."))
        for line in self.line_ids:
            if not line.product_id or not line.product_id.eplus_serial:
                raise UserError(_("Line with missing product E-Plus serial."))
            if line.qty <= 0:
                raise UserError(_("Invalid quantity in a line (<= 0)."))

    # -------------------------------------------------
    # Public: push entrypoint
    # -------------------------------------------------
    def action_push_to_eplus(self):
        self.ensure_one()
        replica_db = self.env["ab_replica_db"].sudo().get_current_from_config()
        if not replica_db:
            raise UserError(_("This is not Replica DB"))

        self.line_ids._recompute_inventory_json()

        self._validate_before_push()
        is_new_customer = self._validate_new_customer()
        if is_new_customer:
            # remove current customer field
            self.customer_id = False

        # todo: eplus_emp_id instead of emp_code
        emp_code = self._get_eplus_emp_id(employee=self.employee_id)

        if not emp_code:
            raise UserError("Employee has no eplus_serial to use! please contact support")
        pc_name = self._get_pc_name()

        bill_typ = 4 if self.customer_id or self.new_customer_name else 1

        conn = self.get_connection()
        if not conn:
            raise UserError(_("Connection to E-Plus failed."))

        try:
            cur = conn.cursor()
            totals = self._compute_header_numbers(cur=cur)

            # 1) Header
            sth_id = self._insert_sales_trans_h(
                cur=cur,
                totals=totals,
                emp_code=emp_code,
                pc_name=pc_name,
                bill_typ=bill_typ,
            )
            if not self._sales_trans_h_exists(cur=cur, sth_id=sth_id):
                raise UserError(
                    _("Header insert failed; header record not found (sth_id=%s).") % sth_id
                )

            # 2) Details
            lines_count = self._insert_sales_trans_d(
                cur=cur,
                sth_id=sth_id,
                emp_code=emp_code,
            )

            if not lines_count:
                raise UserError("BConnect Error no lines_count!\nContact Abdin Support.")

            cur.execute(
                f"UPDATE sales_trans_h SET no_of_items = {PARAM_STR} WHERE sth_id = {PARAM_STR}",
                (int(lines_count or 0), int(sth_id),)
            )

            # 2.5) Bconnect total guard
            self._bconnect_total_guard(cur=cur, sth_id=sth_id)

            # 3) Inventory consumption / updates
            self._update_item_class_store(cur=cur)
            if self.customer_id:
                self._insert_sales_deliv_info(cur, sth_id, emp_code)

            snapshot_vals = self._get_bill_customer_snapshot_vals()
            self.sudo().write({
                'eplus_serial': sth_id,
                'status': 'pending',
                'push_state': 'success',
                'push_message': _("Pushed to E-Plus successfully (sth_id=%s).") % sth_id,
                **snapshot_vals,
            })
            conn.commit()
        except Exception as ex:
            try:
                conn.rollback()
            except Exception:
                pass
            msg = self._format_eplus_error(ex)
            if self.status == "prepending":
                try:
                    self.unlink()
                except Exception:
                    self.sudo().write({
                        'push_state': 'error',
                        'push_message': msg,
                    })
                raise UserError(_("E-Plus push failed: %s") % msg)
            self.sudo().write({
                'push_state': 'error',
                'push_message': msg,
            })
            raise UserError(_("E-Plus push failed: %s") % msg)
        finally:
            try:
                self.line_ids._recompute_inventory_json()
                self.env.cr.commit()
            except Exception:
                pass

    # -------------------------------------------------
    # Private helpers
    # -------------------------------------------------
    def _get_sales_trans_h_notice(self):
        self.ensure_one()
        return self.description or ''

    def _bconnect_total_guard(self, cur, sth_id, tol=0.025):
        cur.execute(
            f"SELECT total_bill FROM sales_trans_h WHERE sth_id = {PARAM_STR}",
            (int(sth_id),),
        )
        row = cur.fetchone()
        total_bill = float(row[0] or 0.0) if row and row[0] is not None else 0.0

        cur.execute(
            f"""
                SELECT COALESCE(SUM(qnty * itm_sell), 0)
                FROM sales_trans_d
                WHERE sth_id = {PARAM_STR}
            """,
            (int(sth_id),),
        )
        row = cur.fetchone()
        total_lines = float(row[0] or 0.0) if row and row[0] is not None else 0.0

        if abs(total_bill - total_lines) > float(tol):
            raise UserError(
                _("BConnect Total Guard failed. Header total (%s) != lines total (%s).")
                % (self._to_2dec(total_bill), self._to_2dec(total_lines))
            )

    def _sales_trans_h_exists(self, cur, sth_id):
        cur.execute(
            f"SELECT 1 FROM sales_trans_h WITH (UPDLOCK, HOLDLOCK) WHERE sth_id = {PARAM_STR}",
            (int(sth_id),),
        )
        return bool(cur.fetchone())

    def _insert_sales_trans_h(self, cur, totals, emp_code, pc_name, bill_typ):
        self.ensure_one()
        rec = self
        if rec.eplus_serial:
            try:
                eplus_serial = int(rec.eplus_serial)
                return eplus_serial
            except Exception as ex:
                pass

        # Use temp_col6 as an idempotency key to avoid duplicate header inserts.
        if rec.id:
            temp_col6 = DB_SERIAL + rec.id
            cur.execute(
                f"""
                    SELECT TOP 1 sth_id
                    FROM sales_trans_h
                    WHERE temp_col6 = {PARAM_STR} AND sto_id = {PARAM_STR}
                    ORDER BY sth_id DESC
                """,
                (temp_col6, int(rec.store_id.eplus_serial)),
            )
            row = cur.fetchone()
            if row and row[0] is not None:
                return int(row[0])

        no_of_items = int(totals['no_of_items'])
        total_bill = totals['total_bill']
        total_bill_after_disc = totals['total_bill_after_disc']

        total_bill_net = totals['total_bill_net']

        total_dis_per = totals['total_dis_per']
        total_des_mon = totals['total_des_mon']
        total_tax = totals['total_tax']
        description = self._get_sales_trans_h_notice()
        if self.new_customer_name:
            description = f"{self.new_customer_name}//{self.new_customer_phone}//{self.new_customer_address}//{description}"

        insert_h_sql = f"""
            INSERT INTO sales_trans_h (
                temp_col6, sto_id, cust_id, bill_typ, no_of_items, no_of_items_exc,
                total_bill, temp_col8, total_bill_exc, total_dis_per, total_des_mon,
                emp_id, sth_notice, sth_cash, sth_rest, sec_insert_uid, sth_flag,
                sth_extra_expenses, total_bill_after_disc, total_bill_net,
                fh_contract_id, fh_company_part, fh_medins_rec_name, fh_medins_ticket_num,
                fh_medins_ins_num, fh_medins_Doc_name, fh_clinic_id, fh_clinic_spec_id,
                fh_doc_spec_id, sec_insert_date, sth_delivery_rest, sth_pc_name,
                sth_pont, sth_pnt_dis, temp_col4, sth_costProfitPerc, total_tax
            )
            VALUES (
                {PARAM_STR}, {PARAM_STR}, {PARAM_STR}, {PARAM_STR}, {PARAM_STR}, {PARAM_STR},
                {PARAM_STR}, {PARAM_STR}, {PARAM_STR}, {PARAM_STR}, {PARAM_STR},
                {PARAM_STR}, {PARAM_STR}, {PARAM_STR}, {PARAM_STR}, {PARAM_STR}, {PARAM_STR},
                {PARAM_STR}, {PARAM_STR}, {PARAM_STR},
                {PARAM_STR}, {PARAM_STR}, {PARAM_STR}, {PARAM_STR},
                {PARAM_STR}, {PARAM_STR}, {PARAM_STR}, {PARAM_STR},
                {PARAM_STR}, GETDATE(), {PARAM_STR}, {PARAM_STR},
                {PARAM_STR}, {PARAM_STR}, {PARAM_STR}, {PARAM_STR}, {PARAM_STR}
            )
        """

        if rec.customer_id.eplus_serial:
            customer_serial = rec.customer_id.eplus_serial
        elif rec.new_customer_name:
            customer_serial = 66803
        else:
            customer_serial = 0
        temp_col6 = DB_SERIAL + rec.id
        h_params = (
            int(temp_col6),  # temp_col6 (odoo header id for idempotency)
            int(rec.store_id.eplus_serial),
            int(customer_serial),
            int(bill_typ),
            no_of_items,
            0,
            total_bill,
            2,
            0,
            total_dis_per,
            total_des_mon,
            emp_code,
            description,
            None,
            None,
            emp_code,
            'P',
            0.00,
            total_bill_after_disc,
            total_bill_net,
            0, 0,
            None, None,
            None, None,
            0,
            16,
            0,
            0,
            pc_name,
            0,
            0,
            None,
            0.0000,
            total_tax,
        )

        cur.execute(insert_h_sql, h_params)

        cur.execute("SELECT CAST(@@IDENTITY AS BIGINT)")
        row = cur.fetchone()
        if row and row[0] is not None:
            return int(row[0])

        raise UserError(
            _("Failed to get new STH ID (SCOPE_IDENTITY/@@IDENTITY/IDENT_CURRENT all returned NULL). "
              "Please check that sales_trans_h.sth_id is an IDENTITY column.")
        )

    ##################### End of _insert_sales_trans_h ############################

    def _insert_sales_trans_d(self, cur, sth_id, emp_code):
        rec = self

        insert_d_sql = f"""
            INSERT INTO sales_trans_d (
                std_id,
                sth_id,
                itm_id,
                c_id,
                exp_date,
                qnty,
                itm_sell,
                itm_cost,
                itm_dis_mon,
                itm_dis_per,
                sec_insert_uid,
                itm_unit,
                itm_aver_cost,
                itm_nexist,
                std_itm_origin,
                itm_tax
            )
            VALUES (
                {PARAM_STR},{PARAM_STR},{PARAM_STR},{PARAM_STR},{PARAM_STR},{PARAM_STR},
                {PARAM_STR},{PARAM_STR},{PARAM_STR},{PARAM_STR},{PARAM_STR},{PARAM_STR},
                {PARAM_STR},{PARAM_STR},{PARAM_STR},{PARAM_STR}
            )
        """

        std_id = 1
        lines_count = 0
        for line in rec.line_ids:
            batches = rec._get_sales_trans_d_batches(cur, line)
            if not batches:
                continue
            batch_gross_total = 0.0
            for batch in batches:
                batch_gross_total += float(batch["qty_for_d"]) * float(batch["price_for_d"] or 0.0)

            for batch in batches:
                dis_mon, dis_per = rec._get_sales_trans_d_discount(line, batch, batch_gross_total)
                params_d = (
                    std_id,
                    int(sth_id),
                    int(line.product_id.eplus_serial),
                    int(batch["source_id"] or 0),
                    batch["exp_date_str"],
                    round(float(batch["qty_for_d"]), 4),
                    rec._to_2dec(batch["price_for_d"]),
                    rec._to_2dec(batch["cost_for_d"]),
                    rec._to_2dec(dis_mon),
                    rec._to_2dec(dis_per),
                    emp_code,
                    int(batch["itm_unit_val"]),
                    rec._to_2dec(batch["avg_cost_for_d"]),
                    int(batch["itm_nexist"]),
                    0,
                    0,
                )
                cur.execute(insert_d_sql, params_d)
                std_id += 1
                lines_count += 1
        return lines_count

    def _get_sales_trans_d_batches(self, cur, line):
        item_factor = self._get_item_catalog_factor(cur, line.product_id.eplus_serial)
        uom_factor = line.uom_id.factor if line.uom_id and line.uom_id.factor else item_factor
        if not uom_factor:
            uom_factor = 1.0
        if not item_factor:
            item_factor = uom_factor or 1.0
        ratio = float(uom_factor) / float(item_factor or 1.0)
        if ratio <= 0:
            ratio = 1.0
        price_ref = self._price_ref_from_line(line, ratio)
        use_small_unit = float(uom_factor or 0) <= 1.0
        qty_small = float(line.qty or 0) * float(uom_factor)
        if qty_small < 0.0001:
            return []

        all_rows = _parse_inventory_json(line)
        batches = []
        for source_id, exp_date_str, qty_to_take, batch_price, batch_cost, itm_nexist in _fifo_batches_for_line(
                qty_small=qty_small,
                product_eplus_serial=line.product_id.eplus_serial,
                sell_price=price_ref,
                all_rows=all_rows,
                store_eplus=self.store_id.eplus_serial,
                allow_fraction=line.product_id.allow_sell_fraction,
                product_name=line.product_id.name,
        ):
            if use_small_unit:
                qty_for_d = float(qty_to_take or 0)
                itm_unit_val = 3
                price_for_d = batch_price / float(item_factor or 1.0)
                cost_for_d = batch_cost / float(item_factor or 1.0)
                avg_cost_for_d = (line.cost or 0.0) / float(item_factor or 1.0)
            else:
                qty_for_d = float(qty_to_take or 0) / float(item_factor or 1.0)
                itm_unit_val = 1
                price_for_d = batch_price
                cost_for_d = batch_cost
                avg_cost_for_d = line.cost or 0.0

            if qty_for_d < 0.0001:
                continue

            batches.append({
                "source_id": int(source_id or 0),
                "exp_date_str": exp_date_str,
                "qty_for_d": float(qty_for_d),
                "price_for_d": float(price_for_d),
                "cost_for_d": float(cost_for_d),
                "itm_unit_val": int(itm_unit_val),
                "avg_cost_for_d": float(avg_cost_for_d),
                "itm_nexist": int(itm_nexist or 0),
            })
        return batches

    def _get_sales_trans_d_discount(self, line, batch, batch_gross_total):
        return 0.0, 0.0

    def _update_item_class_store(self, cur):
        rec = self
        for line in rec.line_ids:
            qty_big = float(line.qty or 0)
            rec._consume_via_json_fifo(
                cur,
                sto_eplus=rec.store_id.eplus_serial,
                itm_eplus=line.product_id.eplus_serial,
                qty_big=qty_big,
                line=line,
            )

    def _insert_sales_deliv_info(self, cur, sth_id, emp_code):
        rec = self

        cust_id_eplus = int(rec.customer_id.eplus_serial or 0)
        snapshot = rec._get_bill_customer_snapshot_vals()
        address = (snapshot.get("bill_customer_address") or "").strip()
        contact = (snapshot.get("bill_customer_name") or "").strip()
        address = f"{contact}\n{address}"
        tel = (snapshot.get("bill_customer_phone") or "").strip()
        if not address:
            address = (rec.invoice_address or "").strip() or (rec.customer_id.address or "")
        if not contact:
            contact = (rec.customer_id.name or "").strip()
        if not tel:
            tel = (rec.customer_id.mobile_phone or "").strip()

        cur.execute(f"DELETE FROM sales_deliv_info WHERE sth_id = {PARAM_STR}", (int(sth_id),))

        insert_sql = f"""
            INSERT INTO sales_deliv_info (
                sth_id,
                address,
                tel,
                contact,
                deliv_emp_id,
                cust_id,
                sec_insert_uid,
                deliv_emp_acc_id
            )
            VALUES (
                {PARAM_STR}, {PARAM_STR}, {PARAM_STR}, {PARAM_STR},
                {PARAM_STR}, {PARAM_STR}, {PARAM_STR}, {PARAM_STR}
            )
        """
        params = (
            int(sth_id),
            address,
            tel,
            contact,
            None,
            cust_id_eplus,
            emp_code,
            None,
        )
        cur.execute(insert_sql, params)

    @api.model
    def _get_item_catalog_factor(self, cur, itm_eplus):
        cur.execute(f"""
            SELECT CAST(itm_unit1_unit3 AS DECIMAL(18,6))
            FROM item_catalog
            WHERE itm_id = {PARAM_STR}
        """, (itm_eplus,))
        row = cur.fetchone()
        if not row or not row[0]:
            return 0.0
        return float(row[0])

    @api.model
    def _consume_via_json_fifo(self, cur, sto_eplus, itm_eplus, qty_big, line):
        """
        FIFO consumption from item_class_store using JSON inventory (dict).
        """
        factor = self._get_item_catalog_factor(cur, itm_eplus)
        uom_factor = line.uom_id.factor if line.uom_id and line.uom_id.factor else factor
        if not uom_factor:
            uom_factor = 1.0
        if not factor:
            factor = uom_factor or 1.0
        ratio = float(uom_factor) / float(factor or 1.0)
        if ratio <= 0:
            ratio = 1.0
        price_ref = self._price_ref_from_line(line, ratio)
        need_small_exact = float(line.qty or 0) * float(uom_factor)
        # POS: always allow fractional quantities
        allow_fraction = True

        if not allow_fraction:
            if not _is_int_units(need_small_exact):
                raise UserError(
                    _("This  product \n%(prod)s\n cannot be sold in fractional small units. "
                      "Requested %(req).4f small units (qty=%(q).4f × factor=%(f).4f). "
                      "Please adjust the quantity to a whole small unit.")
                    % {"req": need_small_exact, "q": float(qty_big), "f": float(factor), "prod": line.product_id.name}
                )
            need_small = int(round(need_small_exact))
        else:
            need_small = need_small_exact

        remain = need_small

        payload = line.inventory_json or {}
        if not isinstance(payload, dict):
            payload = {}
        all_rows_raw = payload.get('data', []) or []

        target_price = float(price_ref or 0.0)
        prod_serial = int(line.product_id.eplus_serial or 0)
        sto_serial = int(sto_eplus or 0)

        all_rows = []
        for r in all_rows_raw:
            try:
                if int(r.get('product_eplus_serial') or 0) != prod_serial:
                    continue
                if int(r.get('store_eplus_serial') or 0) != sto_serial:
                    continue

                q_small = float(r.get('qty_in_small_unit') or 0.0)
                if q_small <= 0:
                    continue

                q_for_batch = _int_floor_units(q_small) if not allow_fraction else q_small
                if q_for_batch <= 0:
                    continue

                price_val = r.get('price')
                try:
                    price_float = float(price_val) if price_val is not None else None
                except Exception:
                    price_float = None

                all_rows.append({
                    'c_id': int(r.get('source_id') or 0),
                    'exp': str(r.get('exp_date') or ''),
                    'qty_small': q_for_batch,
                    'price': price_float,
                })
            except Exception:
                continue

        if not all_rows:
            return

        same_price_rows = [
            rr for rr in all_rows
            if rr['price'] is not None and _eq_price_2dec(rr['price'], target_price)
        ]
        same_price_rows.sort(key=lambda rr: (_parse_dt_to_key(rr['exp']), rr['c_id']))

        for r in same_price_rows:
            if remain <= 0:
                break

            c_id = r['c_id']

            cur.execute(f"""
                SELECT CAST(itm_qty AS DECIMAL(38,6))
                FROM item_class_store WITH (UPDLOCK, ROWLOCK)
                WHERE sto_id = {PARAM_STR} AND itm_id = {PARAM_STR} AND c_id = {PARAM_STR}
            """, (sto_eplus, itm_eplus, c_id))
            row = cur.fetchone()
            avail = float(row[0]) if row and row[0] is not None else 0.0
            if avail <= 0:
                continue

            if not allow_fraction:
                avail_int = _int_floor_units(avail)
                remain_int = int(remain)
                take_small = min(avail_int, int(r['qty_small']), remain_int)
            else:
                take_small = min(avail, float(r['qty_small']), float(remain))

            if take_small <= 0:
                continue

            cur.execute(f"""
                UPDATE item_class_store WITH (ROWLOCK)
                   SET itm_qty = itm_qty - {PARAM_STR},
                       sec_update_date = GETDATE(),
                       sec_update_uid = 1
                 WHERE sto_id = {PARAM_STR} AND itm_id = {PARAM_STR} AND c_id = {PARAM_STR}
            """, (take_small, sto_eplus, itm_eplus, c_id))

            remain -= take_small

        if (remain if allow_fraction else int(remain)) <= 1e-9:
            return

        other_rows = [
            rr for rr in all_rows
            if not (rr['price'] is not None and _eq_price_2dec(rr['price'], target_price))
        ]

        def _other_sort_key(rr):
            price_val = rr['price']
            p = price_val if price_val is not None else float('inf')
            return (p, _parse_dt_to_key(rr['exp']), rr['c_id'])

        other_rows.sort(key=_other_sort_key)

        for r in other_rows:
            if remain <= 0:
                break

            c_id = r['c_id']

            cur.execute(f"""
                SELECT CAST(itm_qty AS DECIMAL(38,6))
                FROM item_class_store WITH (UPDLOCK, ROWLOCK)
                WHERE sto_id = {PARAM_STR} AND itm_id = {PARAM_STR} AND c_id = {PARAM_STR}
            """, (sto_eplus, itm_eplus, c_id))
            row = cur.fetchone()
            avail = float(row[0]) if row and row[0] is not None else 0.0
            if avail <= 0:
                continue

            if not allow_fraction:
                avail_int = _int_floor_units(avail)
                remain_int = int(remain)
                take_small = min(avail_int, int(r['qty_small']), remain_int)
            else:
                take_small = min(avail, float(r['qty_small']), float(remain))

            if take_small <= 0:
                continue

            cur.execute(f"""
                UPDATE item_class_store WITH (ROWLOCK)
                   SET itm_qty = itm_qty - {PARAM_STR},
                       sec_update_date = GETDATE(),
                       sec_update_uid = 1
                 WHERE sto_id = {PARAM_STR} AND itm_id = {PARAM_STR} AND c_id = {PARAM_STR}
            """, (take_small, sto_eplus, itm_eplus, c_id))

            remain -= take_small

    # ----------------- Invoice address datalist ----------------- #
    @api.depends('customer_id')
    def _compute_invoice_address_datalist(self):
        for rec in self:
            invoice_address_list = self.search(
                [('customer_id', '=', rec.customer_id.id)]
            ).mapped('invoice_address')

            invoice_address_list.append(rec.customer_id.address)
            rec.invoice_address_datalist = json.dumps(list(set(invoice_address_list)))

    @api.onchange('customer_id')
    def _onchange_clear_invoice_address(self):
        for rec in self:
            datalist = json.loads(rec.invoice_address_datalist or '[]') if rec.invoice_address_datalist else []
            if len(datalist) == 1:
                rec.invoice_address = datalist[0]
            else:
                rec.invoice_address = ''

    # ---------------------- compute_totals (اللي سألت عليها) ---------------------- #
    @api.depends('line_ids', 'store_id', 'line_ids.product_id', 'line_ids.qty')
    def compute_totals(self):
        for header in self:
            header.total_price = sum(line.net_amount for line in header.line_ids)

            total_net_amount = sum(line.net_amount for line in header.line_ids)
            header.total_net_amount = total_net_amount

            header.number_of_products = len(header.line_ids)

    # ---------------------- Connection helpers ---------------------- #
    def get_connection(self):
        store_ip = self.store_id.ip1
        if self.store_id and not store_ip:
            raise UserError("No IP for this store")
        try:
            with self.connect_eplus(server=store_ip, autocommit=False, charset='UTF-8', param_str=PARAM_STR) as conn:
                if not conn:
                    raise UserError(_("Server %s is offline or too slow") % self.store_id.name)
                return conn
        except Exception:
            raise UserError(_("Server %s is offline or too slow") % self.store_id.name)

    @api.onchange('store_id')
    def _onchange_store_id(self):
        for rec in self:
            if not rec.store_id:
                continue
            if not rec.store_server_online:
                continue
            conn = rec.get_connection()
            if conn:
                rec.line_ids._recompute_inventory_json()

    @api.depends('store_id', 'store_id.ip1')
    def _compute_store_server_online(self):
        for rec in self:
            store_ip = rec.store_id.ip1 if rec.store_id else False
            if not store_ip:
                rec.store_server_online = False
                continue
            try:
                with rec.connect_eplus(
                        server=store_ip,
                        autocommit=False,
                        charset='UTF-8',
                        param_str=PARAM_STR,
                ):
                    rec.store_server_online = True
            except Exception:
                rec.store_server_online = False

    # ---------------------- delete / submit ---------------------- #
    def unlink(self):
        for rec in self:
            if rec.status != 'prepending':
                raise UserError("You Can Only Delete Prepending Bills")
        return super().unlink()

    def action_submit(self):
        """Submit sale."""
        for header in self:
            if not (header.pos_client_token or "").strip():
                raise UserError(_("Submit is only allowed for bills created from POS."))
            header.action_push_to_eplus()
        return True

    @api.model
    def cron_update_status_from_store(self):
        """Mark pending invoices as saved once E-Plus sets sales_trans_h.sth_flag = 'C'."""
        Header = self.env['ab_sales_header'].sudo()
        Store = self.env['ab_store'].sudo()

        pending_headers = Header.search([
            ('status', '=', 'pending'),
            ('eplus_serial', '!=', False),
            ('store_id', '!=', False),
        ])
        if not pending_headers:
            return

        serials_by_store = {}
        for header in pending_headers:
            if not header.store_id:
                continue
            try:
                serial = int(header.eplus_serial or 0)
            except Exception:
                serial = 0
            if not serial:
                continue
            serials_by_store.setdefault(header.store_id.id, []).append(serial)

        if not serials_by_store:
            return

        stores = Store.search([('id', 'in', list(serials_by_store.keys()))])
        store_by_id = {s.id: s for s in stores}

        def _chunks(seq, size):
            for i in range(0, len(seq), size):
                yield seq[i:i + size]

        for store_id, serials in serials_by_store.items():
            store = store_by_id.get(store_id)
            if not store or not store.ip1:
                continue

            serials = list({int(s) for s in serials if s})
            if not serials:
                continue

            try:
                with self.connect_eplus(server=store.ip1, param_str=PARAM_STR, charset='CP1256') as conn:
                    with conn.cursor() as crx:
                        saved_serials = []
                        missing_serials = set()
                        for chunk in _chunks(serials, 2000):
                            placeholders = ",".join([PARAM_STR] * len(chunk))
                            sql = f"""
                                SELECT sth_id, sth_flag
                                FROM sales_trans_h WITH (NOLOCK)
                                WHERE sth_id IN ({placeholders})
                            """
                            params = tuple(chunk)
                            crx.execute(sql, params)
                            rows = crx.fetchall()
                            found_serials = set()
                            for row in rows:
                                try:
                                    sth_id = int(row[0])
                                    sth_flag = (row[1] or "").strip()
                                except Exception:
                                    continue
                                found_serials.add(sth_id)
                                if sth_flag == 'C':
                                    saved_serials.append(sth_id)
                            missing_serials.update(set(chunk) - found_serials)

                        if saved_serials:
                            Header.search([
                                ('status', '=', 'pending'),
                                ('store_id', '=', store.id),
                                ('eplus_serial', 'in', list(set(saved_serials))),
                            ]).write({'status': 'saved'})

                        if missing_serials:
                            headers_to_archive = Header.search([
                                ('status', '=', 'pending'),
                                ('store_id', '=', store.id),
                                ('eplus_serial', 'in', list(missing_serials)),
                                ('active', '=', True),
                            ])
                            if headers_to_archive:
                                headers_to_archive.line_ids.write({'active': False})
                                headers_to_archive.write({'active': False})
            except Exception as ex:
                _logger.error(
                    "Pending status sync failed for store %s (ip=%s): %s",
                    store.display_name, store.ip1, repr(ex),
                )
