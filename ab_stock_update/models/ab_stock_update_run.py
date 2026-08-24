import hashlib
import json
import logging
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from ipaddress import ip_address
from uuid import uuid4

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


_logger = logging.getLogger(__name__)

ZERO_QTY = Decimal("0.00")
MAX_LIVE_ATTEMPTS = 3

STOCK_COLUMNS = (
    "c_id",
    "itm_id",
    "sto_id",
    "ven_id",
    "itm_qty",
    "pharm_price",
    "sell_price",
    "sell_tax",
    "itm_expiry_date",
    "itm_location",
    "sec_insert_uid",
    "sec_insert_date",
    "sec_update_uid",
    "sec_update_date",
)

BUSINESS_COLUMNS = (
    "ven_id",
    "pharm_price",
    "sell_price",
    "sell_tax",
    "itm_expiry_date",
    "itm_location",
)

STOCK_SELECT = """
    SELECT
        CAST(c_id AS BIGINT) AS c_id,
        CAST(itm_id AS BIGINT) AS itm_id,
        CAST(sto_id AS BIGINT) AS sto_id,
        ven_id,
        CAST(ISNULL(itm_qty, 0) AS DECIMAL(18, 2)) AS itm_qty,
        pharm_price,
        sell_price,
        sell_tax,
        itm_expiry_date,
        itm_location,
        sec_insert_uid,
        sec_insert_date,
        sec_update_uid,
        sec_update_date
    FROM dbo.Item_Class_Store {table_hint}
    WHERE sto_id = ?
    {positive_clause}
    ORDER BY itm_id, c_id
"""

UPDATE_STOCK_SQL = """
    UPDATE dbo.Item_Class_Store WITH (ROWLOCK)
       SET itm_qty = ?
     WHERE itm_id = ?
       AND c_id = ?
       AND sto_id = ?
"""

INSERT_STOCK_SQL = """
    INSERT INTO dbo.Item_Class_Store (
        c_id, itm_id, sto_id, ven_id, itm_qty, pharm_price, sell_price,
        sell_tax, itm_expiry_date, itm_location, sec_insert_uid,
        sec_insert_date, sec_update_uid, sec_update_date
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

VERIFY_STOCK_WRITE_SQL = """
    SELECT COUNT_BIG(*) AS row_count,
           CAST(ISNULL(MAX(itm_qty), 0) AS DECIMAL(18, 2)) AS itm_qty
      FROM dbo.Item_Class_Store WITH (HOLDLOCK)
     WHERE itm_id = ?
       AND c_id = ?
       AND sto_id = ?
"""

DELETE_DUPLICATES_SQL = """
    ;WITH ranked AS (
        SELECT *,
               ROW_NUMBER() OVER (
                   PARTITION BY c_id, itm_id, sto_id
                   ORDER BY
                       COALESCE(sec_update_date, sec_insert_date) DESC,
                       sec_insert_date DESC,
                       COALESCE(sec_update_uid, '') DESC,
                       COALESCE(sec_insert_uid, '') DESC
               ) AS duplicate_rank
          FROM dbo.Item_Class_Store WITH (UPDLOCK, HOLDLOCK)
         WHERE itm_id = ?
           AND c_id = ?
           AND sto_id = ?
    )
    DELETE FROM ranked
    OUTPUT
        DELETED.c_id,
        DELETED.itm_id,
        DELETED.sto_id,
        DELETED.ven_id,
        DELETED.itm_qty,
        DELETED.pharm_price,
        DELETED.sell_price,
        DELETED.sell_tax,
        DELETED.itm_expiry_date,
        DELETED.itm_location,
        DELETED.sec_insert_uid,
        DELETED.sec_insert_date,
        DELETED.sec_update_uid,
        DELETED.sec_update_date
    WHERE duplicate_rank > 1
"""


class AbStockUpdateRun(models.Model):
    _name = "ab_stock_update_run"
    _inherit = ["ab_eplus_connect"]
    _description = "Stock Update Run"
    _order = "create_date desc, id desc"

    name = fields.Char(
        string="Transaction Reference",
        required=True,
        readonly=True,
        copy=False,
        index=True,
        default=lambda self: uuid4().hex,
    )
    active = fields.Boolean(default=True)
    store_id = fields.Many2one(
        "ab_store",
        string="Store",
        required=True,
        readonly=True,
        ondelete="restrict",
    )
    sto_id = fields.Integer(string="EPlus Store ID", required=True, readonly=True, index=True)
    branch_ip = fields.Char(string="Branch IP", readonly=True)
    requested_by_id = fields.Many2one(
        "res.users",
        string="Requested By",
        required=True,
        readonly=True,
        default=lambda self: self.env.user,
        ondelete="restrict",
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("previewed", "Previewed"),
            ("applying", "Applying"),
            ("done", "Done"),
            ("drifted", "Drifted"),
            ("failed", "Failed"),
        ],
        required=True,
        readonly=True,
        default="draft",
        index=True,
    )
    previewed_at = fields.Datetime(string="Previewed At", readonly=True)
    applied_at = fields.Datetime(string="Applied At", readonly=True)
    preview_hash = fields.Char(string="Preview Hash", readonly=True)
    attempt_count = fields.Integer(string="Attempts", readonly=True)
    mismatch_count = fields.Integer(string="Mismatched Keys", readonly=True)
    duplicate_group_count = fields.Integer(string="Duplicate Groups", readonly=True)
    blocker_count = fields.Integer(string="Blocking Issues", readonly=True)
    deleted_count = fields.Integer(string="Deleted Rows", readonly=True)
    updated_count = fields.Integer(string="Updated Rows", readonly=True)
    inserted_count = fields.Integer(string="Inserted Rows", readonly=True)
    residual_count = fields.Integer(string="Residual Differences", readonly=True)
    error_message = fields.Text(string="Error", readonly=True)
    line_ids = fields.One2many(
        "ab_stock_update_line",
        "run_id",
        string="Details",
        readonly=True,
    )

    def write(self, values):
        if not self.env.su and set(values) - {"active"}:
            raise AccessError(_("Stock update audit records cannot be modified."))
        return super().write(values)

    def _require_manager(self):
        if not self.env.user.has_group("ab_stock_update.group_ab_stock_update_manager"):
            raise AccessError(_("Only Stock Update Managers can update branch stock."))

    def _get_form_action(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "ab_stock_update.action_ab_stock_update_run"
        )
        action.update(
            {
                "res_id": self.id,
                "view_mode": "form",
                "views": [(False, "form")],
            }
        )
        return action

    @staticmethod
    def _decimal(value):
        if value in (None, False, ""):
            return ZERO_QTY
        return Decimal(str(value)).quantize(Decimal("0.01"))

    @staticmethod
    def _json_default(value):
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        return str(value)

    @classmethod
    def _serialize_row(cls, row):
        return json.dumps(
            {column: row.get(column) for column in STOCK_COLUMNS},
            ensure_ascii=True,
            sort_keys=True,
            default=cls._json_default,
        )

    @classmethod
    def _normalized_value(cls, value):
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        return value

    @classmethod
    def _business_signature(cls, row):
        return tuple(cls._normalized_value(row.get(column)) for column in BUSINESS_COLUMNS)

    @staticmethod
    def _key(row):
        return (int(row["c_id"]), int(row["itm_id"]), int(row["sto_id"]))

    @classmethod
    def _group_rows(cls, rows):
        grouped = defaultdict(list)
        for row in rows:
            grouped[cls._key(row)].append(row)
        return grouped

    @classmethod
    def _positive_quantity(cls, rows):
        return sum(
            (max(cls._decimal(row.get("itm_qty")), ZERO_QTY) for row in rows),
            ZERO_QTY,
        )

    @classmethod
    def _snapshot_hash(cls, branch_rows, main_rows):
        payload = {
            "branch": [cls._serialize_row(row) for row in branch_rows],
            "main": [cls._serialize_row(row) for row in main_rows],
        }
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("ascii")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _fetchall_dict(connection, query, params=()):
        with connection.cursor(as_dict=True) as cursor:
            cursor.execute(query, params)
            return list(cursor.fetchall() or [])

    @classmethod
    def _fetch_stock_rows(cls, connection, sto_id, positive_only=False, lock=False):
        query = STOCK_SELECT.format(
            table_hint="WITH (UPDLOCK, HOLDLOCK)" if lock else "",
            positive_clause="AND itm_qty > 0" if positive_only else "",
        )
        rows = cls._fetchall_dict(connection, query, (int(sto_id),))
        return [
            {column: row.get(column) for column in STOCK_COLUMNS}
            for row in rows
        ]

    @classmethod
    def _get_main_store_row(cls, connection, sto_id, lock=False):
        table_hint = "WITH (UPDLOCK, HOLDLOCK)" if lock else ""
        rows = cls._fetchall_dict(
            connection,
            f"""
                SELECT CAST(sto_id AS BIGINT) AS sto_id,
                       LTRIM(RTRIM(sto_ip1)) AS sto_ip1
                  FROM dbo.Store {table_hint}
                 WHERE sto_id = ?
            """,
            (int(sto_id),),
        )
        if len(rows) != 1:
            raise ValidationError(
                _("EPlus Store ID %(sto_id)s must match exactly one main Store row.")
                % {"sto_id": sto_id}
            )
        branch_ip = (rows[0].get("sto_ip1") or "").strip()
        if not branch_ip:
            raise ValidationError(
                _("EPlus Store ID %(sto_id)s does not have sto_ip1 configured.")
                % {"sto_id": sto_id}
            )
        try:
            ip_address(branch_ip)
        except ValueError as error:
            raise ValidationError(
                _("Branch server %(branch_ip)s is not a valid IP address.")
                % {"branch_ip": branch_ip}
            ) from error
        return {"sto_id": int(rows[0]["sto_id"]), "sto_ip1": branch_ip}

    @classmethod
    def _comparison_lines(cls, branch_rows, main_rows):
        branch_groups = cls._group_rows(branch_rows)
        main_groups = cls._group_rows(main_rows)
        lines = []
        blocker_keys = set()
        sequence = 10

        for key in sorted(branch_groups):
            rows = branch_groups[key]
            if len(rows) <= 1:
                continue
            blocker_keys.add(key)
            branch_qty = cls._positive_quantity(rows)
            lines.append(
                cls._line_values(
                    sequence,
                    key,
                    "blocked",
                    "preview",
                    branch_qty,
                    ZERO_QTY,
                    0,
                    _("The branch contains more than one positive row for this primary key."),
                )
            )
            sequence += 10

        duplicate_group_count = 0
        for key in sorted(main_groups):
            rows = main_groups[key]
            if len(rows) <= 1:
                continue
            duplicate_group_count += 1
            branch_qty = cls._positive_quantity(branch_groups.get(key, []))
            main_qty = cls._positive_quantity(rows)
            signatures = {cls._business_signature(row) for row in rows}
            if len(signatures) > 1:
                blocker_keys.add(key)
                operation = "blocked"
                details = _("Duplicate main rows have different business metadata.")
            else:
                operation = "delete_duplicate"
                details = _("Delete %(count)s extra main rows before updating stock.") % {
                    "count": len(rows) - 1
                }
            lines.append(
                cls._line_values(
                    sequence,
                    key,
                    operation,
                    "preview",
                    branch_qty,
                    main_qty,
                    len(rows),
                    details,
                )
            )
            sequence += 10

        mismatch_count = 0
        for key in sorted(set(branch_groups) | set(main_groups)):
            branch_qty = cls._positive_quantity(branch_groups.get(key, []))
            main_qty = cls._positive_quantity(main_groups.get(key, []))
            if branch_qty == main_qty:
                continue
            mismatch_count += 1
            if key in blocker_keys:
                continue
            if not main_groups.get(key):
                operation = "insert"
                details = _("Insert the missing branch stock row on main.")
            elif branch_qty == ZERO_QTY:
                operation = "zero"
                details = _("Set the retained main row quantity to zero.")
            else:
                operation = "update"
                details = _("Set the retained main row quantity from the branch.")
            lines.append(
                cls._line_values(
                    sequence,
                    key,
                    operation,
                    "preview",
                    branch_qty,
                    main_qty,
                    len(main_groups.get(key, [])),
                    details,
                )
            )
            sequence += 10

        return {
            "lines": lines,
            "mismatch_count": mismatch_count,
            "duplicate_group_count": duplicate_group_count,
            "blocker_count": len(blocker_keys),
        }

    @classmethod
    def _line_values(
        cls,
        sequence,
        key,
        operation,
        status,
        branch_qty,
        main_qty,
        main_row_count,
        details=None,
        attempt=0,
        row_snapshot=None,
    ):
        c_id, itm_id, sto_id = key
        branch_qty = cls._decimal(branch_qty)
        main_qty = cls._decimal(main_qty)
        return {
            "sequence": sequence,
            "attempt": attempt,
            "operation": operation,
            "status": status,
            "c_id": c_id,
            "itm_id": itm_id,
            "sto_id": sto_id,
            "branch_qty": float(branch_qty),
            "main_qty": float(main_qty),
            "difference": float(branch_qty - main_qty),
            "main_row_count": main_row_count,
            "details": details,
            "row_snapshot": row_snapshot,
        }

    def action_preview(self):
        self.ensure_one()
        self._require_manager()
        if self.state != "draft":
            raise UserError(_("Only draft stock update runs can be previewed."))
        if int(self.store_id.eplus_serial or 0) != self.sto_id:
            raise ValidationError(
                _("The Odoo store EPlus Serial changed before preview. Create a new run.")
            )

        with self.connect_eplus(
            param_str="?",
            autocommit=True,
            propagate_error=True,
        ) as main_connection:
            store_row = self._get_main_store_row(main_connection, self.sto_id)
            main_rows = self._fetch_stock_rows(main_connection, self.sto_id)

        with self.connect_eplus(
            server=store_row["sto_ip1"],
            param_str="?",
            autocommit=True,
            propagate_error=True,
        ) as branch_connection:
            branch_rows = self._fetch_stock_rows(
                branch_connection,
                self.sto_id,
                positive_only=True,
            )

        preview = self._comparison_lines(branch_rows, main_rows)
        if preview["lines"]:
            self.env["ab_stock_update_line"].sudo().create(
                [dict(values, run_id=self.id) for values in preview["lines"]]
            )
        self.sudo().write(
            {
                "branch_ip": store_row["sto_ip1"],
                "state": "previewed",
                "previewed_at": fields.Datetime.now(),
                "preview_hash": self._snapshot_hash(branch_rows, main_rows),
                "mismatch_count": preview["mismatch_count"],
                "duplicate_group_count": preview["duplicate_group_count"],
                "blocker_count": preview["blocker_count"],
                "error_message": False,
            }
        )
        return True

    def action_open_apply_confirmation(self):
        self.ensure_one()
        self._require_manager()
        if self.state != "previewed":
            raise UserError(_("Only previewed stock update runs can be applied."))
        if self.blocker_count:
            raise UserError(_("Resolve all blocking issues before applying this run."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Confirm Stock Update"),
            "res_model": "ab_stock_update_confirm_wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_run_id": self.id},
        }

    def _durable_audit(self, run_values=None, line_values=None):
        self.ensure_one()
        with self.env.registry.cursor() as cursor:
            audit_env = api.Environment(cursor, SUPERUSER_ID, {})
            audit_run = audit_env[self._name].browse(self.id).exists()
            if not audit_run:
                return
            if line_values:
                audit_env["ab_stock_update_line"].create(
                    [dict(values, run_id=audit_run.id) for values in line_values]
                )
            if run_values:
                audit_run.write(run_values)
            cursor.commit()
        self.invalidate_recordset()

    def _claim_for_apply(self):
        self.ensure_one()
        with self.env.registry.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(%s, %s)",
                (190019, int(self.sto_id)),
            )
            cursor.execute(
                """
                    SELECT id
                      FROM ab_stock_update_run
                     WHERE sto_id = %s
                       AND state = 'applying'
                       AND id != %s
                     LIMIT 1
                """,
                (int(self.sto_id), self.id),
            )
            if cursor.fetchone():
                raise UserError(
                    _("Another stock update is already applying for this store.")
                )
            cursor.execute(
                """
                    SELECT state, blocker_count
                      FROM ab_stock_update_run
                     WHERE id = %s
                     FOR UPDATE
                """,
                (self.id,),
            )
            row = cursor.fetchone()
            if not row or row[0] != "previewed":
                raise UserError(_("Only previewed stock update runs can be applied."))
            if row[1]:
                raise UserError(_("Resolve all blocking issues before applying this run."))
            audit_env = api.Environment(cursor, SUPERUSER_ID, {})
            audit_env[self._name].browse(self.id).write(
                {
                    "state": "applying",
                    "error_message": False,
                    "attempt_count": 0,
                    "deleted_count": 0,
                    "updated_count": 0,
                    "inserted_count": 0,
                    "residual_count": 0,
                }
            )
            cursor.commit()
        self.invalidate_recordset()

    @classmethod
    def _validate_apply_rows(cls, branch_groups, main_groups):
        for key, rows in branch_groups.items():
            if len(rows) > 1:
                raise ValidationError(
                    _("Branch primary key %(key)s has more than one positive row.")
                    % {"key": key}
                )
        for key, rows in main_groups.items():
            if len(rows) <= 1:
                continue
            if len({cls._business_signature(row) for row in rows}) > 1:
                raise ValidationError(
                    _("Duplicate main key %(key)s has conflicting business metadata.")
                    % {"key": key}
                )

    @classmethod
    def _delete_main_duplicates(cls, connection, branch_groups, main_groups, attempt):
        lines = []
        sequence = attempt * 100000
        for key in sorted(main_groups):
            rows = main_groups[key]
            if len(rows) <= 1:
                continue
            c_id, itm_id, sto_id = key
            with connection.cursor(as_dict=True) as cursor:
                cursor.execute(DELETE_DUPLICATES_SQL, (itm_id, c_id, sto_id))
                deleted_rows = list(cursor.fetchall() or [])
            if len(deleted_rows) != len(rows) - 1:
                raise ValidationError(
                    _(
                        "Duplicate cleanup for key %(key)s deleted %(actual)s rows; "
                        "expected %(expected)s."
                    )
                    % {
                        "key": key,
                        "actual": len(deleted_rows),
                        "expected": len(rows) - 1,
                    }
                )
            branch_qty = cls._positive_quantity(branch_groups.get(key, []))
            for deleted_row in deleted_rows:
                normalized = {
                    column: deleted_row.get(column) for column in STOCK_COLUMNS
                }
                deleted_qty = cls._decimal(normalized.get("itm_qty"))
                lines.append(
                    cls._line_values(
                        sequence,
                        key,
                        "delete_duplicate",
                        "deleted",
                        branch_qty,
                        deleted_qty,
                        len(rows),
                        _("Deleted an extra main row for this compound key."),
                        attempt=attempt,
                        row_snapshot=cls._serialize_row(normalized),
                    )
                )
                sequence += 1
        return lines

    @classmethod
    def _apply_quantities(cls, connection, branch_groups, main_groups, attempt):
        lines = []
        sequence = attempt * 100000 + 50000
        with connection.cursor() as cursor:
            for key in sorted(set(branch_groups) | set(main_groups)):
                c_id, itm_id, sto_id = key
                branch_rows = branch_groups.get(key, [])
                main_rows = main_groups.get(key, [])
                branch_qty = cls._positive_quantity(branch_rows)
                main_qty = cls._positive_quantity(main_rows)
                if branch_qty == main_qty:
                    continue

                if main_rows:
                    operation = "zero" if branch_qty == ZERO_QTY else "update"
                    cursor.execute(
                        UPDATE_STOCK_SQL,
                        (branch_qty, itm_id, c_id, sto_id),
                    )
                    cursor.execute(VERIFY_STOCK_WRITE_SQL, (itm_id, c_id, sto_id))
                    row_count, written_qty = cursor.fetchone()
                    if (
                        int(row_count or 0) != 1
                        or cls._decimal(written_qty) != branch_qty
                    ):
                        raise ValidationError(
                            _("Stock update for key %(key)s did not affect exactly one row.")
                            % {"key": key}
                        )
                    details = (
                        _("Set the retained main row quantity to zero.")
                        if operation == "zero"
                        else _("Updated the retained main row from branch stock.")
                    )
                    row_snapshot = None
                    status = "applied"
                else:
                    if len(branch_rows) != 1:
                        raise ValidationError(
                            _("Missing main key %(key)s has no unique positive branch row.")
                            % {"key": key}
                        )
                    operation = "insert"
                    source_row = branch_rows[0]
                    cursor.execute(
                        INSERT_STOCK_SQL,
                        tuple(source_row.get(column) for column in STOCK_COLUMNS),
                    )
                    cursor.execute(VERIFY_STOCK_WRITE_SQL, (itm_id, c_id, sto_id))
                    row_count, written_qty = cursor.fetchone()
                    if (
                        int(row_count or 0) != 1
                        or cls._decimal(written_qty) != branch_qty
                    ):
                        raise ValidationError(
                            _("Stock insert for key %(key)s did not affect exactly one row.")
                            % {"key": key}
                        )
                    details = _("Inserted the complete missing branch row on main.")
                    row_snapshot = cls._serialize_row(source_row)
                    status = "inserted"

                lines.append(
                    cls._line_values(
                        sequence,
                        key,
                        operation,
                        status,
                        branch_qty,
                        main_qty,
                        len(main_rows),
                        details,
                        attempt=attempt,
                        row_snapshot=row_snapshot,
                    )
                )
                sequence += 1
        return lines

    @classmethod
    def _residual_lines(cls, branch_rows, main_rows, attempt):
        branch_groups = cls._group_rows(branch_rows)
        main_groups = cls._group_rows(main_rows)
        lines = []
        sequence = attempt * 100000 + 90000
        for key in sorted(main_groups):
            rows = main_groups[key]
            if len(rows) <= 1:
                continue
            lines.append(
                cls._line_values(
                    sequence,
                    key,
                    "residual",
                    "residual",
                    cls._positive_quantity(branch_groups.get(key, [])),
                    cls._positive_quantity(rows),
                    len(rows),
                    _("Main still contains duplicate rows for this key."),
                    attempt=attempt,
                )
            )
            sequence += 1
        for key in sorted(set(branch_groups) | set(main_groups)):
            branch_qty = cls._positive_quantity(branch_groups.get(key, []))
            main_qty = cls._positive_quantity(main_groups.get(key, []))
            if branch_qty == main_qty:
                continue
            lines.append(
                cls._line_values(
                    sequence,
                    key,
                    "residual",
                    "residual",
                    branch_qty,
                    main_qty,
                    len(main_groups.get(key, [])),
                    _("Branch and main quantities still differ after verification."),
                    attempt=attempt,
                )
            )
            sequence += 1
        return lines

    @staticmethod
    def _reset_main_session(connection):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
                cursor.execute("SET LOCK_TIMEOUT -1")
                cursor.execute("SET DEADLOCK_PRIORITY NORMAL")
                cursor.execute("SET XACT_ABORT OFF")
        except Exception:
            _logger.exception("Could not restore the pooled main SQL session settings.")
            try:
                connection.close()
            except Exception:
                _logger.exception("Could not close the main SQL session after reset failure.")

    def _execute_attempt(self, attempt):
        self.ensure_one()
        main_connection = None
        operation_lines = []
        with self.connect_eplus(
            server=self.branch_ip,
            param_str="?",
            autocommit=True,
            propagate_error=True,
        ) as branch_connection:
            branch_before = self._fetch_stock_rows(
                branch_connection,
                self.sto_id,
                positive_only=True,
            )
            branch_before_hash = self._snapshot_hash(branch_before, [])
            branch_groups = self._group_rows(branch_before)

            try:
                with self.connect_eplus(
                    param_str="?",
                    autocommit=False,
                    propagate_error=True,
                ) as main_connection:
                    main_connection.rollback()
                    with main_connection.cursor() as cursor:
                        cursor.execute("SET XACT_ABORT ON")
                        cursor.execute("SET DEADLOCK_PRIORITY LOW")
                        cursor.execute("SET LOCK_TIMEOUT 10000")
                        cursor.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")

                    store_row = self._get_main_store_row(
                        main_connection,
                        self.sto_id,
                        lock=True,
                    )
                    if store_row["sto_ip1"] != self.branch_ip:
                        raise ValidationError(
                            _("The branch IP changed after preview. Create a new stock update run.")
                        )

                    main_before = self._fetch_stock_rows(
                        main_connection,
                        self.sto_id,
                        lock=True,
                    )
                    main_groups = self._group_rows(main_before)
                    self._validate_apply_rows(branch_groups, main_groups)

                    operation_lines.extend(
                        self._delete_main_duplicates(
                            main_connection,
                            branch_groups,
                            main_groups,
                            attempt,
                        )
                    )
                    main_after_delete = self._fetch_stock_rows(
                        main_connection,
                        self.sto_id,
                        lock=True,
                    )
                    main_groups = self._group_rows(main_after_delete)
                    if any(len(rows) > 1 for rows in main_groups.values()):
                        raise ValidationError(_("Main still contains duplicate stock keys."))

                    operation_lines.extend(
                        self._apply_quantities(
                            main_connection,
                            branch_groups,
                            main_groups,
                            attempt,
                        )
                    )

                    branch_after = self._fetch_stock_rows(
                        branch_connection,
                        self.sto_id,
                        positive_only=True,
                    )
                    if self._snapshot_hash(branch_after, []) != branch_before_hash:
                        main_connection.rollback()
                        self._reset_main_session(main_connection)
                        for values in operation_lines:
                            values["status"] = "rolled_back"
                            values["details"] = _(
                                "Rolled back because branch stock changed during synchronization."
                            )
                        return {"committed": False, "retry": True, "lines": operation_lines}

                    pending_main = self._fetch_stock_rows(
                        main_connection,
                        self.sto_id,
                        lock=True,
                    )
                    residual = self._residual_lines(branch_after, pending_main, attempt)
                    if residual:
                        raise ValidationError(
                            _("Pending main stock did not match the stable branch snapshot.")
                        )
                    main_connection.commit()
                    self._reset_main_session(main_connection)
                    return {"committed": True, "retry": False, "lines": operation_lines}
            except Exception:
                if main_connection is not None:
                    try:
                        main_connection.rollback()
                        self._reset_main_session(main_connection)
                    except Exception:
                        _logger.exception("Could not roll back main stock update transaction.")
                        try:
                            main_connection.close()
                        except Exception:
                            _logger.exception("Could not close the failed main SQL session.")
                raise

    def _verify_live(self, attempt):
        self.ensure_one()
        with self.connect_eplus(
            param_str="?",
            autocommit=True,
            propagate_error=True,
        ) as main_connection:
            store_row = self._get_main_store_row(main_connection, self.sto_id)
            if store_row["sto_ip1"] != self.branch_ip:
                raise ValidationError(
                    _("The branch IP changed during final verification.")
                )
            main_rows = self._fetch_stock_rows(main_connection, self.sto_id)
        with self.connect_eplus(
            server=self.branch_ip,
            param_str="?",
            autocommit=True,
            propagate_error=True,
        ) as branch_connection:
            branch_rows = self._fetch_stock_rows(
                branch_connection,
                self.sto_id,
                positive_only=True,
            )
        return self._residual_lines(branch_rows, main_rows, attempt)

    def action_apply_confirmed(self):
        self.ensure_one()
        self._require_manager()
        if self.state != "previewed":
            raise UserError(_("Only previewed stock update runs can be applied."))
        if self.blocker_count:
            raise UserError(_("Resolve all blocking issues before applying this run."))

        self._claim_for_apply()
        committed_lines = []
        last_residual = []
        try:
            for attempt in range(1, MAX_LIVE_ATTEMPTS + 1):
                result = self._execute_attempt(attempt)
                self._durable_audit(
                    run_values={"attempt_count": attempt},
                    line_values=result["lines"],
                )
                if result["retry"]:
                    continue

                committed_lines.extend(result["lines"])
                last_residual = self._verify_live(attempt)
                if last_residual:
                    self._durable_audit(line_values=last_residual)
                    if attempt < MAX_LIVE_ATTEMPTS:
                        continue
                    break

                counts = self._operation_counts(committed_lines)
                self._durable_audit(
                    run_values={
                        "state": "done",
                        "applied_at": fields.Datetime.now(),
                        "deleted_count": counts["deleted"],
                        "updated_count": counts["updated"],
                        "inserted_count": counts["inserted"],
                        "residual_count": 0,
                        "error_message": False,
                    }
                )
                return self._get_form_action()

            counts = self._operation_counts(committed_lines)
            self._durable_audit(
                run_values={
                    "state": "drifted",
                    "applied_at": fields.Datetime.now(),
                    "deleted_count": counts["deleted"],
                    "updated_count": counts["updated"],
                    "inserted_count": counts["inserted"],
                    "residual_count": len(last_residual),
                    "error_message": _(
                        "Live branch activity prevented stock convergence "
                        "after %(attempts)s attempts."
                    )
                    % {"attempts": MAX_LIVE_ATTEMPTS},
                }
            )
            return self._get_form_action()
        except Exception as error:
            _logger.exception("Stock update run %s failed.", self.name)
            counts = self._operation_counts(committed_lines)
            self._durable_audit(
                run_values={
                    "state": "failed",
                    "applied_at": fields.Datetime.now(),
                    "deleted_count": counts["deleted"],
                    "updated_count": counts["updated"],
                    "inserted_count": counts["inserted"],
                    "residual_count": len(last_residual),
                    "error_message": str(error),
                }
            )
            raise UserError(_("Stock update failed: %s") % error) from error

    @staticmethod
    def _operation_counts(lines):
        return {
            "deleted": sum(
                1
                for values in lines
                if values["operation"] == "delete_duplicate"
                and values["status"] == "deleted"
            ),
            "updated": sum(
                1
                for values in lines
                if values["operation"] in ("update", "zero")
                and values["status"] == "applied"
            ),
            "inserted": sum(
                1
                for values in lines
                if values["operation"] == "insert"
                and values["status"] == "inserted"
            ),
        }


class AbStockUpdateLine(models.Model):
    _name = "ab_stock_update_line"
    _description = "Stock Update Detail"
    _order = "attempt, sequence, id"

    run_id = fields.Many2one(
        "ab_stock_update_run",
        required=True,
        readonly=True,
        index=True,
        ondelete="restrict",
    )
    sequence = fields.Integer(readonly=True)
    attempt = fields.Integer(readonly=True)
    operation = fields.Selection(
        selection=[
            ("update", "Update"),
            ("zero", "Set to Zero"),
            ("insert", "Insert"),
            ("delete_duplicate", "Delete Duplicate"),
            ("blocked", "Blocked"),
            ("residual", "Residual Difference"),
        ],
        required=True,
        readonly=True,
    )
    status = fields.Selection(
        selection=[
            ("preview", "Preview"),
            ("applied", "Applied"),
            ("inserted", "Inserted"),
            ("deleted", "Deleted"),
            ("rolled_back", "Rolled Back"),
            ("residual", "Residual"),
        ],
        required=True,
        readonly=True,
    )
    c_id = fields.Integer(string="Class ID", required=True, readonly=True, index=True)
    itm_id = fields.Integer(string="Item ID", required=True, readonly=True, index=True)
    sto_id = fields.Integer(string="Store ID", required=True, readonly=True, index=True)
    branch_qty = fields.Float(string="Branch Stock", digits=(18, 2), readonly=True)
    main_qty = fields.Float(string="Main Stock", digits=(18, 2), readonly=True)
    difference = fields.Float(string="Difference", digits=(18, 2), readonly=True)
    main_row_count = fields.Integer(string="Main Row Count", readonly=True)
    details = fields.Text(readonly=True)
    row_snapshot = fields.Text(string="Row Snapshot", readonly=True)
