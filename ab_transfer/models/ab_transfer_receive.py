# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.sql import column_exists, rename_column

_logger = logging.getLogger(__name__)


class AbTransferReceiveHeader(models.Model):
    _name = "ab_transfer_receive_header"
    _inherit = ["ab_eplus_connect"]
    _description = "Transfer Receive Queue"
    _order = "sec_insert_date desc, transfer_serial desc"
    _rec_name = "display_name"

    display_name = fields.Char(
        string="Transfer",
        compute="_compute_display_name",
        store=True,
    )

    transfer_serial = fields.Integer(
        string="Transfer Serial",
        required=True,
        index=True,
        readonly=True,
    )
    from_store_sql_id = fields.Integer(
        string="From Store ID",
        required=True,
        readonly=True,
    )
    to_store_sql_id = fields.Integer(
        string="To Store ID",
        required=True,
        readonly=True,
    )
    from_store_id = fields.Many2one(
        "ab_store",
        string="From Store",
        readonly=True,
    )
    to_store_id = fields.Many2one(
        "ab_store",
        string="To Store",
        readonly=True,
    )
    from_store_name = fields.Char(
        string="From Store Name",
        readonly=True,
    )
    to_store_name = fields.Char(
        string="To Store Name",
        readonly=True,
    )
    items_count = fields.Integer(
        string="Items Count",
        readonly=True,
    )
    sec_insert_date = fields.Datetime(
        string="Transfer Date",
        readonly=True,
    )
    stnh_toh_id = fields.Integer(
        string="TOH ID",
        readonly=True,
    )
    employee_name = fields.Char(
        string="Employee",
        readonly=True,
    )
    notes = fields.Char(
        string="Notes",
        readonly=True,
    )
    total_sell_value = fields.Float(
        string="Total Sale",
        digits=(16, 3),
        readonly=True,
    )
    total_cost_value = fields.Float(
        string="Total Cost",
        digits=(16, 3),
        readonly=True,
    )
    destination_activated = fields.Boolean(
        string="Destination Active",
        readonly=True,
    )

    line_ids = fields.One2many(
        "ab_transfer_receive_line",
        "header_id",
        string="Items",
        readonly=True,
    )
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("received", "Received"),
        ],
        string="Receive Status",
        default="pending",
        required=True,
        readonly=True,
        index=True,
    )
    received_at = fields.Datetime(
        string="Received At",
        readonly=True,
        copy=False,
    )
    error_message = fields.Text(
        string="Error",
        readonly=True,
        copy=False,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
        readonly=True,
    )

    _uniq_transfer_receive = models.Constraint(
        "UNIQUE(transfer_serial, from_store_sql_id, to_store_sql_id)",
        "EPlus transfer already exists in the receive queue.",
    )

    def _auto_init(self):
        self._rename_existing_columns({
            "stnh_id": "transfer_serial",
            "eplus_error_message": "error_message",
        })
        return super()._auto_init()

    def _rename_existing_columns(self, renames):
        for old_name, new_name in renames.items():
            if (
                column_exists(self.env.cr, self._table, old_name)
                and not column_exists(self.env.cr, self._table, new_name)
            ):
                rename_column(self.env.cr, self._table, old_name, new_name)

    @api.depends("transfer_serial", "from_store_name", "to_store_name")
    def _compute_display_name(self):
        for rec in self:
            if rec.transfer_serial:
                rec.display_name = _("Receive %s") % rec.transfer_serial
            else:
                rec.display_name = _("Transfer Receive")

    def web_read(self, specification):
        self._check_current_branch_access()
        return super().web_read(specification)

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("receive_sync"):
            raise UserError(_("Transfer receive records are loaded from EPlus. Manual creation is not allowed."))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get("receive_sync"):
            raise UserError(_("Transfer receive records are managed from EPlus and cannot be edited manually."))
        return super().write(vals)

    def unlink(self):
        if not self.env.context.get("receive_sync"):
            raise UserError(_("Transfer receive records cannot be deleted manually."))
        return super().unlink()

    @api.model
    def _get_current_branch_store(self):
        store = self._get_branch_connection_store()
        if not (store.ip1 or store.ip2):
            raise UserError(_("Current branch store MSSQL server IP is missing."))
        return store

    @api.model
    def _get_allowed_branch_stores(self):
        try:
            replica_db = self.env["ab_replica_db"].sudo().get_current_from_config()
        except Exception:
            return self.env["ab_store"].browse()
        if not replica_db:
            return self.env["ab_store"].browse()
        return replica_db.allowed_sales_store_ids.filtered("allow_sale")

    @api.model
    def _get_allowed_branch_sql_ids(self):
        return sorted({
            int(store.eplus_serial)
            for store in self._get_allowed_branch_stores()
            if store.eplus_serial
        })

    @api.model
    def _get_branch_connection_store(self):
        Header = self.env["ab_transfer_header"].sudo()
        store = Header._get_default_source_store()
        if store and (store.ip1 or store.ip2):
            return store
        stores = self._get_allowed_branch_stores().filtered(lambda branch: branch.ip1 or branch.ip2)
        if stores:
            return stores[0]
        raise UserError(_("No allowed Transfer From Store has an MSSQL server IP configured."))

    @api.model
    def _get_receive_sync_stores(self):
        return self._get_allowed_branch_stores().filtered(
            lambda store: store.eplus_serial and (store.ip1 or store.ip2)
        )

    @api.model
    def _get_branch_sql_connection(self, store=None):
        store = store or self._get_branch_connection_store()
        return self.connect_eplus(
            server=store.ip1 or store.ip2,
            param_str="?",
            autocommit=False,
            propagate_error=True,
        )

    @api.model
    def _get_current_branch_sql_id(self):
        branch_sql_ids = self._get_allowed_branch_sql_ids()
        if not branch_sql_ids:
            raise UserError(_("No allowed Transfer From Store has an EPlus serial configured."))
        return branch_sql_ids[0]

    def _get_receive_connection_store(self):
        self.ensure_one()
        store = self.to_store_id
        if not store and self.to_store_sql_id:
            store = self.env["ab_store"].sudo().search(
                [("eplus_serial", "=", self.to_store_sql_id)],
                limit=1,
            )
        if store and (store.ip1 or store.ip2):
            return store
        return self._get_branch_connection_store()

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, **kwargs):
        if not self.env.context.get("skip_receive_branch_filter"):
            try:
                branch_sql_ids = self._get_allowed_branch_sql_ids()
            except Exception:
                _logger.exception("Could not determine current branch for transfer receive search.")
                branch_sql_ids = []
            branch_domain = [("to_store_sql_id", "in", branch_sql_ids)] if branch_sql_ids else [("to_store_sql_id", "=", 0)]
            domain = fields.Domain.AND([
                domain if domain is not None else [],
                branch_domain,
            ])
        return super()._search(domain, offset=offset, limit=limit, order=order, **kwargs)

    def _check_current_branch_access(self):
        if self.env.context.get("skip_receive_branch_filter"):
            return True
        branch_sql_ids = set(self._get_allowed_branch_sql_ids())
        forbidden = self.filtered(
            lambda rec: rec.to_store_sql_id and rec.to_store_sql_id not in branch_sql_ids
        )
        if forbidden:
            raise UserError(_("You can only access transfers assigned to the current branch."))
        return True

    @api.model
    def cron_sync_pending_receives(self):
        try:
            self.sudo()._sync_pending(raise_on_error=False)
        except Exception:
            _logger.exception("Scheduled transfer receive pending sync failed.")
        return True

    def action_sync_pending_receives(self):
        self.env["ab_transfer_receive_header"]._sync_pending(raise_on_error=True)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Pending Receives"),
                "message": _("Pending receives and lines were synced successfully."),
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }

    @api.model
    def _sync_pending(self, raise_on_error=True):
        if self.env.context.get("skip_receive_sync"):
            return True
        sync_stores = self._get_receive_sync_stores()
        if not sync_stores:
            message = _("No allowed Transfer From Store has both EPlus serial and MSSQL server IP configured.")
            if raise_on_error:
                raise UserError(message)
            _logger.warning(message)
            return False
        pending_keys = set()
        rows = []
        synced_branch_sql_ids = []
        errors = []

        for store in sync_stores:
            branch_sql_id = int(store.eplus_serial or 0)
            try:
                store_rows = self._fetch_pending_rows_from_store(store, branch_sql_id)
                rows.extend(store_rows)
                synced_branch_sql_ids.append(branch_sql_id)
            except Exception as exc:
                _logger.exception("Transfer receive pending sync failed for store %s.", store.display_name)
                errors.append("%s: %s" % (store.display_name, exc))

        if errors and raise_on_error:
            raise UserError(_("Failed to sync pending receives:\n%s") % "\n".join(errors))
        if not synced_branch_sql_ids:
            return False

        sync_model = self.with_context(receive_sync=True, skip_receive_sync=True).sudo()
        stores_by_serial = self._get_stores_by_eplus_serial(rows)
        existing = sync_model.search([
            ("to_store_sql_id", "in", synced_branch_sql_ids),
        ])
        existing_by_key = {
            (rec.transfer_serial, rec.from_store_sql_id, rec.to_store_sql_id): rec
            for rec in existing
        }

        for row in rows:
            values = self._pending_row_to_values(row, stores_by_serial)
            key = (values["transfer_serial"], values["from_store_sql_id"], values["to_store_sql_id"])
            pending_keys.add(key)
            record = existing_by_key.get(key)
            if record:
                record.write(values)
            else:
                sync_model.create(values)

        stale = existing.filtered(
            lambda rec: rec.state == "pending"
            and (rec.transfer_serial, rec.from_store_sql_id, rec.to_store_sql_id) not in pending_keys
        )
        if stale:
            stale.write({"state": "received"})
        pending_records = sync_model.search([
            ("to_store_sql_id", "in", synced_branch_sql_ids),
            ("state", "=", "pending"),
        ])
        try:
            pending_records._sync_lines_from_eplus()
        except Exception as exc:
            _logger.exception("Transfer receive pending line sync failed.")
            if raise_on_error:
                raise UserError(_("Pending receives synced, but line sync failed:\n%s") % exc)
            return False
        return True

    @api.model
    def _fetch_pending_rows_from_store(self, store, branch_sql_id):
        with self._get_branch_sql_connection(store) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT stnh_id, stnh_f_Sto_id, stnh_t_Sto_id,
                           s1.sto_name_ar s1Name,
                           s2.sto_name_ar s2Name,
                           stnh_no_items,
                           sth.sec_insert_date,
                           ISNULL(stnh_toh_id,0) stnh_toh_id,
                           e_name,
                           stnh_notes,
                           stnh_tot_sell_value,
                           stnh_tot_cost_value,
                           s2.activated,
                           CASE stnh_flag
                                WHEN 'S' THEN 'لم يستلم'
                                WHEN 'R' THEN 'تم إستلامه'
                           END dState
                    FROM Store_Trans_h sth
                    JOIN store s1 ON s1.sto_id = stnh_f_Sto_id
                    JOIN store s2 ON s2.sto_id = stnh_t_Sto_id
                    LEFT JOIN employee e ON e.e_id = sth.sec_insert_uid
                    WHERE stnh_flag = 'S'
                      AND stnh_t_Sto_id = ?
                    """,
                    (branch_sql_id,),
                )
                return cursor.fetchall() or []

    @api.model
    def _get_stores_by_eplus_serial(self, rows):
        serials = set()
        for row in rows:
            serials.add(int(row[1] or 0))
            serials.add(int(row[2] or 0))
        serials.discard(0)
        if not serials:
            return {}
        stores = self.env["ab_store"].sudo().search([("eplus_serial", "in", list(serials))])
        return {
            int(store.eplus_serial): store.id
            for store in stores
            if store.eplus_serial
        }

    @api.model
    def _pending_row_to_values(self, row, stores_by_serial):
        from_store_sql_id = int(row[1] or 0)
        to_store_sql_id = int(row[2] or 0)
        return {
            "transfer_serial": int(row[0] or 0),
            "from_store_sql_id": from_store_sql_id,
            "to_store_sql_id": to_store_sql_id,
            "from_store_id": stores_by_serial.get(from_store_sql_id) or False,
            "to_store_id": stores_by_serial.get(to_store_sql_id) or False,
            "from_store_name": row[3] or "",
            "to_store_name": row[4] or "",
            "items_count": int(row[5] or 0),
            "sec_insert_date": row[6] or False,
            "stnh_toh_id": int(row[7] or 0),
            "employee_name": row[8] or "",
            "notes": row[9] or "",
            "total_sell_value": float(row[10] or 0.0),
            "total_cost_value": float(row[11] or 0.0),
            "destination_activated": bool(row[12]),
            "state": "pending",
            "company_id": self.env.company.id,
        }

    def _sync_lines_from_eplus(self):
        sync_line = self.env["ab_transfer_receive_line"].with_context(receive_sync=True).sudo()
        products_by_serial = {}
        for rec in self:
            if rec.state != "pending":
                continue
            with rec._get_branch_sql_connection(rec._get_receive_connection_store()) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT stnh_f_Sto_id,
                               stnh_t_Sto_id,
                               s1.sto_name_ar s1Name,
                               s2.sto_name_ar s2Name,
                               st.stnh_id,
                               st.st_itm_id,
                               st.st_itm_quantity,
                               st.st_itm_pharm_price,
                               st.st_itm_received_qty,
                               st.st_c_id,
                               ic.itm_code,
                               ic.itm_name_ar
                        FROM Store_Trans st
                        JOIN Store_Trans_h sth
                            ON st.stnh_id = sth.stnh_id
                           AND st.st_from_store = sth.stnh_f_Sto_id
                           AND st.st_to_store = sth.stnh_t_Sto_id
                        JOIN store s1 ON s1.sto_id = stnh_f_Sto_id
                        JOIN store s2 ON s2.sto_id = stnh_t_Sto_id
                        JOIN Item_Catalog ic ON ic.itm_id = st.st_itm_id
                        WHERE stnh_flag = 'S'
                          AND st.stnh_id = ?
                          AND st.st_from_store = ?
                          AND st.st_to_store = ?
                        """,
                        (rec.transfer_serial, rec.from_store_sql_id, rec.to_store_sql_id),
                    )
                    rows = cursor.fetchall() or []
                if not rows:
                    rec.line_ids.with_context(receive_sync=True).sudo().unlink()
                    rec.with_context(receive_sync=True).sudo().write({"state": "received"})
                    continue
                products_by_serial.update(self._get_products_by_eplus_serial(rows))
                rec.line_ids.with_context(receive_sync=True).sudo().unlink()
                sync_line.create([
                    rec._line_row_to_values(row, products_by_serial)
                    for row in rows
                ])
        return True

    @api.model
    def _get_products_by_eplus_serial(self, rows):
        serials = {int(row[5] or 0) for row in rows if row[5]}
        if not serials:
            return {}
        products = self.env["ab_product"].sudo().search([("eplus_serial", "in", list(serials))])
        return {
            int(product.eplus_serial): product.id
            for product in products
            if product.eplus_serial
        }

    def _line_row_to_values(self, row, products_by_serial):
        self.ensure_one()
        product_sql_id = int(row[5] or 0)
        transferred_qty = float(row[6] or 0.0)
        received_qty = float(row[8] or 0.0)
        return {
            "header_id": self.id,
            "transfer_serial": int(row[4] or 0),
            "from_store_sql_id": int(row[0] or 0),
            "to_store_sql_id": int(row[1] or 0),
            "from_store_name": row[2] or "",
            "to_store_name": row[3] or "",
            "product_sql_id": product_sql_id,
            "product_id": products_by_serial.get(product_sql_id) or False,
            "product_code": row[10] or "",
            "product_name": row[11] or "",
            "class_id": int(row[9] or 0),
            "transferred_qty": transferred_qty,
            "pharm_price": float(row[7] or 0.0),
            "received_qty": received_qty,
            "receive_qty": max(transferred_qty - received_qty, 0.0),
            "company_id": self.env.company.id,
        }

    def action_post_receive(self):
        self.ensure_one()
        self._check_current_branch_access()
        if self.state != "pending":
            raise UserError(_("Only pending transfers can be received."))
        self._sync_lines_from_eplus()
        self.invalidate_recordset(["state", "line_ids"])
        if self.state != "pending":
            raise UserError(_("This transfer is no longer pending in EPlus."))
        if not self.line_ids:
            raise UserError(_("No pending lines were found for this transfer."))
        self._validate_receive_lines_before_post()
        received_item_count = len(self.line_ids.filtered(lambda line: line.receive_qty > 0))

        try:
            with self._get_branch_sql_connection(self._get_receive_connection_store()) as conn:
                cursor = conn.cursor()
                try:
                    self._post_receive_to_eplus(cursor)
                    self.with_context(receive_sync=True).sudo().write({
                        "state": "received",
                        "received_at": fields.Datetime.now(),
                        "error_message": False,
                    })
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise
                finally:
                    cursor.close()
            _logger.info(
                "Transfer received: transfer_serial=%s source_store=%s/%s destination_store=%s/%s received_item_count=%s user=%s",
                self.transfer_serial,
                self.from_store_sql_id,
                self.from_store_name,
                self.to_store_sql_id,
                self.to_store_name,
                received_item_count,
                self.env.user.display_name,
            )
            return {"type": "ir.actions.client", "tag": "reload"}
        except Exception as exc:
            error_message = str(exc)
            _logger.exception("EPlus transfer receive failed for transfer_serial %s", self.transfer_serial)
            self.with_context(receive_sync=True).sudo().write({"error_message": error_message})
            raise ValidationError(_("Failed to receive transfer:\n%s") % error_message)

    def _validate_receive_lines_before_post(self):
        self.ensure_one()
        missing_product_lines = self.line_ids.filtered(lambda line: not line.product_id)
        if missing_product_lines:
            missing_items = []
            for line in missing_product_lines[:10]:
                missing_items.append(
                    "%s%s" % (
                        line.product_sql_id,
                        " - %s" % (line.product_name or line.product_code) if (line.product_name or line.product_code) else "",
                    )
                )
            extra_count = len(missing_product_lines) - len(missing_items)
            if extra_count > 0:
                missing_items.append(_("and %s more") % extra_count)
            raise ValidationError(
                _(
                    "Some EPlus items do not exist in Odoo products. "
                    "Create/link products by EPlus serial (itm_id) before receiving: %s"
                )
                % ", ".join(missing_items)
            )

    def _post_receive_to_eplus(self, cursor):
        self.ensure_one()
        branch_sql_ids = set(self._get_allowed_branch_sql_ids())
        if self.to_store_sql_id not in branch_sql_ids:
            raise ValidationError(
                _("Destination store is not allowed for the current branch.")
            )
        update_user_sql_id = self._get_receive_user_sql_id()
        cursor.execute(
            """
            SELECT stnh_flag
            FROM Store_Trans_h WITH (UPDLOCK, HOLDLOCK)
            WHERE stnh_id = ?
              AND stnh_f_Sto_id = ?
              AND stnh_t_Sto_id = ?
            """,
            (self.transfer_serial, self.from_store_sql_id, self.to_store_sql_id),
        )
        row = cursor.fetchone()
        if not row:
            raise ValidationError(_("EPlus transfer header was not found."))
        if row[0] != "S":
            raise ValidationError(_("This transfer was already received in EPlus."))

        for line in self.line_ids.filtered(lambda item: item.receive_qty > 0):
            class_id = int(line.class_id or 0)
            product_sql_id = int(line.product_sql_id or 0)
            self._ensure_destination_stock_row(
                cursor,
                line,
                class_id,
                self.to_store_sql_id,
                product_sql_id,
                update_user_sql_id,
            )
            cursor.execute(
                """
                UPDATE Item_Class_Store
                SET itm_qty = ISNULL(itm_qty, 0) + ?,
                    sec_update_uid = ?,
                    sec_update_date = GETDATE()
                WHERE c_id = ?
                  AND sto_id = ?
                  AND itm_id = ?
                """,
                (
                    float(line.receive_qty or 0.0),
                    str(update_user_sql_id),
                    class_id,
                    self.to_store_sql_id,
                    product_sql_id,
                ),
            )
            if cursor.rowcount == 0:
                raise ValidationError(
                    _("Failed to update destination stock row for product %s.")
                    % (line.product_display_name or line.product_sql_id)
                )

        cursor.execute(
            """
            UPDATE Store_Trans_h
            SET stnh_flag = 'R'
            WHERE stnh_id = ?
              AND stnh_f_Sto_id = ?
              AND stnh_t_Sto_id = ?
              AND stnh_flag = 'S'
            """,
            (self.transfer_serial, self.from_store_sql_id, self.to_store_sql_id),
        )
        if cursor.rowcount == 0:
            raise ValidationError(_("EPlus transfer header was not found for receive flag update."))
        self._insert_receive_replication_trans(cursor, update_user_sql_id)

    def _insert_receive_replication_trans(self, cursor, update_user_sql_id):
        self.ensure_one()
        transfer_serial = int(self.transfer_serial or 0)
        from_store_sql_id = int(self.from_store_sql_id or 0)
        to_store_sql_id = int(self.to_store_sql_id or 0)
        update_user_sql_id = int(update_user_sql_id or 0)
        trans_qry = (
            "Update Store_Trans_h set  stnh_flag='R' ,sec_update_date=getdate() , "
            "sec_update_uid= %s WHERE stnh_id=%s AND stnh_f_Sto_id=%s AND stnh_t_Sto_id=%s"
            % (update_user_sql_id, transfer_serial, from_store_sql_id, to_store_sql_id)
        )
        cursor.execute(
            """
            INSERT INTO Replication_Trans (trans_typ_1,
                                           trans_typ_2,
                                           store_id,
                                           store_id2,
                                           itm_id,
                                           class_id,
                                           class_id_ext1,
                                           class_id_ext2,
                                           itm_qty,
                                           itm_expire,
                                           general_id,
                                           general_name,
                                           trans_qry,
                                           sec_insert_uid,
                                           form_nm,
                                           ePlusVersion)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                10,
                2,
                from_store_sql_id,
                to_store_sql_id,
                0,
                0,
                0,
                0,
                0,
                None,
                transfer_serial,
                " Recive Ezn Sarf %s" % transfer_serial,
                trans_qry,
                update_user_sql_id,
                "Recieve_Store_Trans_ar",
                "e-Plus",
            ),
        )

    def _ensure_destination_stock_row(self, cursor, line, class_id, store_sql_id, product_sql_id, update_user_sql_id):
        cursor.execute(
            """
            SELECT 1
            FROM Item_Class_Store WITH (UPDLOCK, HOLDLOCK)
            WHERE c_id = ?
              AND sto_id = ?
              AND itm_id = ?
            """,
            (class_id, store_sql_id, product_sql_id),
        )
        if cursor.fetchone():
            return

        available_columns = self._get_item_class_store_columns(cursor)
        source_values = self._get_source_stock_row_values(cursor, line, available_columns)
        stock_values = self._get_transfer_stock_values(cursor, line)

        values_by_column = dict(source_values)
        expressions_by_column = {}

        def set_param(column_name, value):
            actual_column = available_columns.get(column_name.lower())
            if actual_column:
                values_by_column[actual_column.lower()] = value
                expressions_by_column.pop(actual_column.lower(), None)

        def set_sql(column_name, expression):
            actual_column = available_columns.get(column_name.lower())
            if actual_column:
                expressions_by_column[actual_column.lower()] = expression
                values_by_column.pop(actual_column.lower(), None)

        set_param("c_id", class_id)
        set_param("sto_id", store_sql_id)
        set_param("itm_id", product_sql_id)
        set_param("itm_qty", 0)
        set_param("itm_expiry_date", stock_values.get("itm_expiry_date"))
        set_param("pharm_price", stock_values.get("pharm_price"))
        set_param("sell_price", stock_values.get("sell_price"))
        set_param("sell_tax", stock_values.get("sell_tax"))
        set_param("itm_cost", stock_values.get("cost"))
        set_param("cost", stock_values.get("cost"))
        set_param("avg_cost", stock_values.get("cost"))
        set_param("average_cost", stock_values.get("cost"))
        set_param("itm_aver_cost", stock_values.get("cost"))
        set_param("sec_insert_uid", update_user_sql_id)
        set_sql("sec_insert_date", "GETDATE()")
        set_param("sec_update_uid", update_user_sql_id)
        set_sql("sec_update_date", "GETDATE()")

        if not {"c_id", "sto_id", "itm_id", "itm_qty"}.issubset(set(available_columns)):
            raise ValidationError(_("Item_Class_Store key columns were not found."))

        columns = []
        expressions = []
        params = []
        for column_key, actual_column in available_columns.items():
            if column_key in expressions_by_column:
                columns.append(self._quote_sql_identifier(actual_column))
                expressions.append(expressions_by_column[column_key])
            elif column_key in values_by_column:
                columns.append(self._quote_sql_identifier(actual_column))
                expressions.append("?")
                params.append(values_by_column[column_key])

        cursor.execute(
            """
            INSERT INTO Item_Class_Store (%s)
            VALUES (%s)
            """
            % (", ".join(columns), ", ".join(expressions)),
            tuple(params),
        )

    def _get_item_class_store_columns(self, cursor):
        cursor.execute(
            """
            SELECT c.name
            FROM sys.columns c
            JOIN sys.objects o ON o.object_id = c.object_id
            WHERE o.name = 'Item_Class_Store'
              AND c.is_identity = 0
              AND c.is_computed = 0
              AND c.system_type_id <> 189
            ORDER BY c.column_id
            """
        )
        return {
            str(row[0]).lower(): str(row[0])
            for row in (cursor.fetchall() or [])
            if row and row[0]
        }

    def _get_source_stock_row_values(self, cursor, line, available_columns):
        if not available_columns:
            return {}
        columns = list(available_columns.values())
        select_columns = ", ".join(
            "src.%s" % self._quote_sql_identifier(column)
            for column in columns
        )
        cursor.execute(
            """
            SELECT %s
            FROM Item_Class_Store src
            WHERE src.c_id = ?
              AND src.sto_id = ?
              AND src.itm_id = ?
            """
            % select_columns,
            (
                int(line.class_id or 0),
                self.from_store_sql_id,
                int(line.product_sql_id or 0),
            ),
        )
        row = cursor.fetchone()
        if not row:
            return {}
        return {
            columns[index].lower(): row[index]
            for index in range(len(columns))
        }

    def _get_transfer_stock_values(self, cursor, line):
        cursor.execute(
            """
            SELECT st.st_itm_expiry,
                   st.st_itm_pharm_price,
                   st.st_itm_cost,
                   st.st_itm_sell,
                   st.st_itm_tax
            FROM Store_Trans st
            WHERE st.stnh_id = ?
              AND st.st_from_store = ?
              AND st.st_to_store = ?
              AND st.st_c_id = ?
              AND st.st_itm_id = ?
            """,
            (
                self.transfer_serial,
                self.from_store_sql_id,
                self.to_store_sql_id,
                int(line.class_id or 0),
                int(line.product_sql_id or 0),
            ),
        )
        row = cursor.fetchone()
        if not row:
            raise ValidationError(_("EPlus transfer line was not found for destination stock creation."))

        transfer_expiry = row[0]
        transfer_pharm_price = row[1]
        transfer_cost = row[2]
        transfer_sell_price = row[3]
        transfer_sell_tax = row[4]

        return {
            "itm_expiry_date": transfer_expiry,
            "pharm_price": transfer_pharm_price,
            "sell_price": transfer_sell_price,
            "sell_tax": transfer_sell_tax,
            "cost": transfer_cost if transfer_cost is not None else transfer_pharm_price,
        }

    @staticmethod
    def _quote_sql_identifier(identifier):
        return "[%s]" % str(identifier).replace("]", "]]")

    def _get_receive_user_sql_id(self):
        Header = self.env["ab_transfer_header"]
        user_id = Header._default_user_id()
        if not user_id:
            raise UserError(_("Current user has no linked EPlus cost center."))
        user = self.env["ab_costcenter"].browse(user_id).exists()
        return Header.new({})._get_ref_id(user, _("Receive User"))


class AbTransferReceiveLine(models.Model):
    _name = "ab_transfer_receive_line"
    _description = "Transfer Receive Queue Line"
    _order = "id"

    header_id = fields.Many2one(
        "ab_transfer_receive_header",
        string="Receive Header",
        required=True,
        ondelete="cascade",
    )
    transfer_serial = fields.Integer(
        string="Transfer Number",
        required=True,
        readonly=True,
    )
    from_store_sql_id = fields.Integer(
        string="Store EPlus ID",
        readonly=True,
    )
    to_store_sql_id = fields.Integer(
        string="Store ID",
        readonly=True,
    )
    from_store_name = fields.Char(
        string="From Store Name",
        readonly=True,
    )
    to_store_name = fields.Char(
        string="To Store Name",
        readonly=True,
    )
    product_sql_id = fields.Integer(
        string="Product ID",
        required=True,
        readonly=True,
    )
    product_id = fields.Many2one(
        "ab_product",
        string="Product",
        readonly=True,
    )
    product_code = fields.Char(
        string="Product Code",
        readonly=True,
    )
    product_name = fields.Char(
        string="Product Name",
        readonly=True,
    )
    product_display_name = fields.Char(
        string="Product",
        compute="_compute_product_display_name",
        store=True,
    )
    class_id = fields.Integer(
        string="Class ID",
        required=True,
        readonly=True,
    )
    transferred_qty = fields.Float(
        string="Transferred Qty",
        digits=(16, 3),
        readonly=True,
    )
    pharm_price = fields.Float(
        string="Pharm Price",
        digits=(16, 3),
        readonly=True,
    )
    received_qty = fields.Float(
        string="Received Qty",
        digits=(16, 3),
        readonly=True,
    )
    receive_qty = fields.Float(
        string="Receive Qty",
        digits=(16, 3),
        readonly=True,
    )
    state = fields.Selection(
        related="header_id.state",
        readonly=True,
        store=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
        readonly=True,
    )

    def _auto_init(self):
        self._rename_existing_columns({
            "stnh_id": "transfer_serial",
            "eplus_received_qty": "received_qty",
        })
        return super()._auto_init()

    def _rename_existing_columns(self, renames):
        for old_name, new_name in renames.items():
            if (
                column_exists(self.env.cr, self._table, old_name)
                and not column_exists(self.env.cr, self._table, new_name)
            ):
                rename_column(self.env.cr, self._table, old_name, new_name)

    @api.depends("product_id", "product_code", "product_name", "product_sql_id")
    def _compute_product_display_name(self):
        for rec in self:
            if rec.product_id:
                rec.product_display_name = rec.product_id.display_name
            else:
                rec.product_display_name = "[%s] %s" % (
                    rec.product_code or rec.product_sql_id or "",
                    rec.product_name or "",
                )

    def web_read(self, specification):
        self._check_current_branch_access()
        return super().web_read(specification)

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, **kwargs):
        if not self.env.context.get("skip_receive_branch_filter"):
            try:
                branch_sql_ids = self.env["ab_transfer_receive_header"]._get_allowed_branch_sql_ids()
            except Exception:
                _logger.exception("Could not determine current branch for transfer receive line search.")
                branch_sql_ids = []
            branch_domain = [("to_store_sql_id", "in", branch_sql_ids)] if branch_sql_ids else [("to_store_sql_id", "=", 0)]
            domain = fields.Domain.AND([
                domain if domain is not None else [],
                branch_domain,
            ])
        return super()._search(domain, offset=offset, limit=limit, order=order, **kwargs)

    def _check_current_branch_access(self):
        if self.env.context.get("skip_receive_branch_filter"):
            return True
        branch_sql_ids = set(self.env["ab_transfer_receive_header"]._get_allowed_branch_sql_ids())
        forbidden = self.filtered(
            lambda rec: rec.to_store_sql_id and rec.to_store_sql_id not in branch_sql_ids
        )
        if forbidden:
            raise UserError(_("You can only access transfer receive lines assigned to the current branch."))
        return True

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("receive_sync"):
            raise UserError(_("Transfer receive lines are loaded from EPlus. Manual creation is not allowed."))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get("receive_sync"):
            raise UserError(_("Transfer receive lines cannot be edited manually."))
        return super().write(vals)

    def unlink(self):
        if not self.env.context.get("receive_sync"):
            raise UserError(_("Transfer receive lines cannot be deleted manually."))
        return super().unlink()
