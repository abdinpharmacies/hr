# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError

PARAM_STR = "?"


class AbSalesCashierCloseWizard(models.TransientModel):
    _name = "ab_sales_cashier_close_wizard"
    _description = "Sales Cashier Close Wizard"

    user_id = fields.Many2one(
        "res.users",
        string="Current User",
        readonly=True,
        default=lambda self: self.env.user.id,
    )
    close_time = fields.Datetime(
        string="Close Time",
        readonly=True,
        default=fields.Datetime.now,
    )
    store_id = fields.Many2one(
        "ab_store",
        string="Store",
        required=True,
        readonly=True,
    )
    employee_id = fields.Many2one(
        "ab_hr_employee",
        string="Cashier Employee",
        required=True,
        domain=lambda self: [
            "|",
            ("user_id", "=", self.env.user.id),
            "&",
            ("user_id", "!=", False),
            ("costcenter_id.eplus_serial", "!=", False),
        ],
        default=lambda self: self._default_employee_id(),
    )
    line_ids = fields.One2many(
        "ab_sales_cashier_close_wizard_line",
        "wizard_id",
        string="Wallet Balances",
    )

    @api.model
    def _safe_int(self, value, default=0):
        try:
            return int(value)
        except Exception:
            return default

    @api.model
    def _safe_float(self, value, default=0.0):
        try:
            return float(value)
        except Exception:
            return default

    @api.model
    def _default_employee_id(self):
        employee = self.env["ab_hr_employee"].sudo().search(
            [("user_id", "=", self.env.user.id)],
            limit=1,
        )
        return employee.id or False

    @api.model
    def _employee_eplus_id(self, employee):
        if not employee:
            return 1
        eplus_id = self._safe_int(employee.costcenter_id.eplus_serial if employee.costcenter_id else 0, 0)
        return eplus_id or 1

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        api_model = self.env["ab_sales_cashier_api"]
        api_model._require_cashier_access()

        requested_store_id = self.env.context.get("default_store_id") or self.env.context.get("store_id")
        store = api_model._coerce_store(
            store_id=requested_store_id,
            required=True,
            require_connection=True,
        )
        res["store_id"] = store.id
        if not res.get("employee_id"):
            employee_id = self._default_employee_id()
            if employee_id:
                res["employee_id"] = employee_id

        wallets = api_model._fetch_store_wallets_from_bconnect(store=store)
        res["line_ids"] = [
            (0, 0, {
                "wallet_id": int(wallet["id"]),
                "wallet_name": wallet.get("name", ""),
                "opening_balance": wallet.get("balance", 0.0),
                "net_balance": wallet.get("balance", 0.0),
            })
            for wallet in wallets
            if self._safe_int(wallet.get("id"), 0)
        ]
        return res

    def action_confirm_close(self):
        self.ensure_one()
        api_model = self.env["ab_sales_cashier_api"]
        api_model._require_cashier_access()

        if not self.employee_id:
            raise UserError(_("Please select cashier employee."))

        store = api_model._coerce_store(
            store_id=self.store_id.id,
            required=True,
            require_connection=True,
        )
        employee_eplus_id = self._employee_eplus_id(self.employee_id)

        with api_model.connect_eplus(
            server=store.ip1,
            param_str=PARAM_STR,
            charset="CP1256",
            autocommit=False,
            propagate_error=True,
        ) as conn:
            try:
                with conn.cursor(as_dict=True) as cur:
                    for line in self.line_ids:
                        wallet_id = self._safe_int(line.wallet_id, 0)
                        if not wallet_id:
                            continue
                        net_balance = self._safe_float(line.net_balance, 0.0)
                        cur.execute(
                            f"""
                                SELECT TOP (1) fcs_id
                                FROM F_Cash_Store WITH (UPDLOCK, ROWLOCK)
                                WHERE fcs_id = {PARAM_STR}
                                  AND ISNULL(fcs_active, 0) = 1
                                  AND ISNULL(fcs_type, 0) = 1
                            """,
                            (wallet_id,),
                        )
                        if not (cur.fetchall() or []):
                            raise UserError(_("Wallet %s was not found.") % (wallet_id,))
                        cur.execute(
                            f"""
                                UPDATE F_Cash_Store WITH (ROWLOCK)
                                   SET fcs_current_balance = {PARAM_STR},
                                       sec_update_uid = {PARAM_STR},
                                       sec_update_date = GETDATE()
                                 WHERE fcs_id = {PARAM_STR}
                                   AND ISNULL(fcs_active, 0) = 1
                                   AND ISNULL(fcs_type, 0) = 1
                            """,
                            (net_balance, employee_eplus_id, wallet_id),
                        )
                conn.commit()
            except Exception:
                conn.rollback()
                raise

        return {"type": "ir.actions.act_window_close"}


class AbSalesCashierCloseWizardLine(models.TransientModel):
    _name = "ab_sales_cashier_close_wizard_line"
    _description = "Sales Cashier Close Wizard Line"

    wizard_id = fields.Many2one(
        "ab_sales_cashier_close_wizard",
        required=True,
        ondelete="cascade",
    )
    wallet_id = fields.Integer(string="Wallet ID", readonly=True)
    wallet_name = fields.Char(string="Wallet", readonly=True)
    opening_balance = fields.Float(string="Opening Balance", readonly=True, digits=(16, 4))
    net_balance = fields.Float(string="Net Balance", required=True, digits=(16, 4))
