# -*- coding: utf-8 -*-

import logging

from odoo import models
from odoo.exceptions import UserError
from odoo.tools.translate import _

PARAM_STR = "?"
_logger = logging.getLogger(__name__)


class AbSalesReturnHeaderReplicationTransInherit(models.Model):
    _inherit = "ab_sales_return_header"

    def action_push_to_eplus_return(self):
        result = super().action_push_to_eplus_return()
        for rec in self:
            rec._insert_replication_trans_rows_for_return()
        return result

    def _insert_replication_trans_rows_for_return(self):
        self.ensure_one()
        if self.status != "saved":
            return

        lines = self.line_ids.filtered(lambda l: float(l.qty or 0.0) > 0 and l.itm_eplus_id and l.c_id)
        if not lines:
            return

        store_id = int(self.sto_eplus_serial or 0)
        sth_id = int(self.origin_header_id or 0)
        emp_id = int(self.env["ab_sales_header"]._get_eplus_emp_id() or 0)
        if not store_id or not sth_id or not emp_id:
            raise UserError(_("Missing required values to insert Replication_Trans rows."))

        conn = self.get_connection()
        if not conn:
            raise UserError(_("Connection to B-Connect failed while inserting Replication_Trans."))

        try:
            cur = conn.cursor()
            cur.execute(
                f"""
                    INSERT INTO Replication_Trans (
                        trans_typ_1, trans_typ_2,
                        store_id, general_id, general_name, trans_qry,
                        sec_insert_uid, form_nm
                    )
                    VALUES (
                        {PARAM_STR}, {PARAM_STR},
                        {PARAM_STR}, {PARAM_STR}, {PARAM_STR}, {PARAM_STR},
                        {PARAM_STR}, {PARAM_STR}
                    )
                """,
                (
                    8, 1,
                    store_id, sth_id, "Sales Return", "",
                    emp_id, "Sales_returning_ar",
                ),
            )

            for line in lines:
                item_id = int(line.itm_eplus_id or 0)
                class_id = int(line.c_id or 0)
                line_store_id = int(line.sto_id or store_id)
                qty = float(line._qty_to_source_unit() or 0.0)
                source_factor = float(line._get_source_factor() or 1.0)
                qty_small = qty * source_factor
                qty_expr = format(qty_small, "g")
                trans_qry = (
                    " UPDATE Item_Class_Store SET  itm_qty=itm_qty +"
                    f"{qty_expr} "
                    f",sec_update_uid='{emp_id}',sec_update_date=getdate() "
                    f"WHERE itm_id={item_id} AND c_id={class_id} AND sto_id={line_store_id}"
                )
                cur.execute(
                    f"""
                        INSERT INTO Replication_Trans (
                            trans_typ_1, trans_typ_2, store_id,
                            itm_id, class_id, class_id_ext1, class_id_ext2,
                            itm_qty, itm_expire,
                            general_id, general_name, trans_qry,
                            sec_insert_uid, form_nm, ePlusVersion
                        )
                        VALUES (
                            {PARAM_STR}, {PARAM_STR}, {PARAM_STR},
                            {PARAM_STR}, {PARAM_STR}, {PARAM_STR}, {PARAM_STR},
                            {PARAM_STR}, {PARAM_STR},
                            {PARAM_STR}, {PARAM_STR}, {PARAM_STR},
                            {PARAM_STR}, {PARAM_STR}, {PARAM_STR}
                        )
                    """,
                    (
                        1, 1, store_id,
                        item_id, class_id, 0, 0,
                        qty, None,
                        0, "Item_Class_store", trans_qry,
                        emp_id, "Sales_returning_ar", "e-Plus",
                    ),
                )

            conn.commit()
        except Exception as ex:
            try:
                conn.rollback()
            except Exception as rollback_ex:
                _logger.warning(repr(rollback_ex))
            raise UserError(
                _("E-Plus return was saved, but Replication_Trans insert failed: %s") % repr(ex)
            )

    def action_server_insert_replication_trans_rows(self):
        records = self
        if not records:
            active_ids = self.env.context.get("active_ids") or []
            records = self.browse(active_ids)
        if not records:
            raise UserError(_("No Sales Return records selected."))

        done = 0
        skipped = 0
        failed = 0
        errors = []

        for rec in records:
            if rec.status != "saved":
                skipped += 1
                continue
            if not rec.store_id or not rec.store_id.ip1:
                failed += 1
                errors.append(_("#%s: Store IP is missing.") % rec.id)
                continue
            try:
                rec._insert_replication_trans_rows_for_return()
                done += 1
            except Exception as ex:
                failed += 1
                errors.append(_("#%s: %s") % (rec.id, str(ex)))

        severity = "success" if failed == 0 else "warning"
        message = _("Done: %(done)s, Skipped: %(skipped)s, Failed: %(failed)s") % {
            "done": done,
            "skipped": skipped,
            "failed": failed,
        }
        if errors:
            message = "%s\n%s" % (message, "\n".join(errors[:5]))

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Replication_Trans Bulk Insert"),
                "message": message,
                "type": severity,
                "sticky": failed > 0,
            },
        }
