import json
import re
from datetime import datetime, time
from decimal import Decimal, ROUND_HALF_EVEN


from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import UserError, ValidationError

PARAM_STR = '?'



# ======================= JSON helpers (line.inventory_json = dict) ======================= #


# ======================= Model: AbdinSalesHeader ======================= #

class AbdinSalesHeader(models.Model):
    _name = 'ab_sales_header'
    _description = 'ab_sales_header'
    _rec_name = 'id'
    _order = 'id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']


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
    employee_delivery_id = fields.Many2one('ab_hr_employee')
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
        string="Actual Salesperson",
        domain=lambda self: [
            "|",
            ("user_id", "=", self.env.user.id),
            "&",
            ("user_id", "!=", False),
            ("costcenter_id.code", "!=", False),
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

    @api.model
    def get_sales_dashboard_payload(self):
        today = fields.Date.context_today(self)
        today_start = fields.Datetime.to_string(datetime.combine(today, time.min))

        Header = self.env["ab_sales_header"]

        pending_bills = Header.search_count([("status", "=", "pending")])
        saved_bills_today = Header.search_count([
            ("status", "=", "saved"),
            ("write_date", ">=", today_start),
        ])

        return {
            "updated_at": fields.Datetime.to_string(fields.Datetime.now()),
            "quick_actions": [
                {
                    "key": "pos",
                    "title": _("POS"),
                    "icon": "fa-shopping-cart",
                    "tone": "primary",
                    "action": "ab_sales.ab_sales_pos_action",
                },
                {
                    "key": "bill_wizard",
                    "title": _("Bill Wizard"),
                    "icon": "fa-magic",
                    "tone": "teal",
                    "action": "ab_sales.ab_sales_bill_wizard_action",
                },
                {
                    "key": "sales_details",
                    "title": _("Sales Details"),
                    "icon": "fa-list",
                    "tone": "slate",
                    "action": "ab_sales.ab_sales_line_action",
                },
            ],
            "metrics": [
                {
                    "key": "pending_bills",
                    "label": _("Pending Bills"),
                    "value": pending_bills,
                    "icon": "fa-clock-o",
                    "tone": "warning",
                    "action": {
                        "type": "ir.actions.act_window",
                        "name": _("Pending Bills"),
                        "res_model": "ab_sales_header",
                        "view_mode": "list,form",
                        "views": [[False, "list"], [False, "form"]],
                        "domain": [["status", "=", "pending"]],
                    },
                },
                {
                    "key": "saved_bills_today",
                    "label": _("Saved Bills Today"),
                    "value": saved_bills_today,
                    "icon": "fa-check-circle",
                    "tone": "success",
                    "action": {
                        "type": "ir.actions.act_window",
                        "name": _("Saved Bills Today"),
                        "res_model": "ab_sales_header",
                        "view_mode": "list,form",
                        "views": [[False, "list"], [False, "form"]],
                        "domain": [
                            ["status", "=", "saved"],
                            ["write_date", ">=", today_start],
                        ],
                    },
                },
            ],
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
        self.check_access('read')
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
            return_header = (ReturnHeader._create_callcenter_order)({
                'store_id': self.store_id.id,
                'origin_header_id': int(self.eplus_serial),
            })
        return return_header.with_context(curr_target='new').action_load_lines()

    # --------------------- New customer validation --------------------- #
    def _validate_new_customer(self):
        rec = self
        flds = [
            rec.new_customer_name,
            rec.new_customer_phone,
            rec.new_customer_address
        ]

        if any(flds):
            if not all(flds):
                raise UserError(_("All 'New Customer' fields must set!"))

            # Name
            if rec.new_customer_name:
                name = rec.new_customer_name.strip()

                # Arabic only + space + - + _
                if not re.fullmatch(r'^[\u0600-\u06FF\s\-_]+$', name):
                    raise ValidationError(
                        _("Name must contain Arabic characters only. Allowed symbols: - _")
                    )

                words = name.split()

                # At least two words
                if len(words) < 2:
                    raise ValidationError(
                        _("Name must contain at least two words.")
                    )

                # Each word at least 2 chars
                if any(len(w) < 2 for w in words):
                    raise ValidationError(
                        _("Each word must contain at least 2 characters.")
                    )

            else:
                raise ValidationError(_("Name is required."))

            # Mobile
            if rec.new_customer_phone:
                if not re.fullmatch(r'01[0125]\d{8}', rec.new_customer_phone):
                    raise ValidationError(
                        _("Mobile number must be 11 digits and start with 010, 011, 012, or 015.")
                    )
            else:
                raise ValidationError(_("Mobile phone is required."))

            # Address
            if rec.new_customer_address:
                if len(rec.new_customer_address.strip()) < 2:
                    raise ValidationError(
                        _("Address must be at least 2 characters long.")
                    )
            else:
                raise ValidationError(_("Address is required."))

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
    def _to_4dec(self, val):
        value = float(Decimal(val or 0).quantize(Decimal('0.0001'), rounding=ROUND_HALF_EVEN))
        return value

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


    # -------------------------------------------------
    # Public: push entrypoint
    # -------------------------------------------------

    # -------------------------------------------------
    # Private helpers
    # -------------------------------------------------




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


    # ---------------------- delete / submit ---------------------- #
    def unlink(self):
        for rec in self:
            if rec.status != 'prepending':
                raise UserError("You Can Only Delete Prepending Bills")
        return super().unlink()
