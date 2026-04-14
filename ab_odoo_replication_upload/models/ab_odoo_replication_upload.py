# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.tools.translate import _
from odoo.exceptions import UserError
from odoo.addons.ab_odoo_connect import OdooConnectionSingleton
import logging
from odoo.tools import config
from odoo.addons.queue_job.exception import RetryableJobError

REPL_DB = config.get('repl_db', 0)
_logger = logging.getLogger(__name__)


class OdooReplicationUpload(models.AbstractModel):
    _name = 'ab_odoo_replication_upload'
    _description = 'ab_odoo_replication_upload'

    no_delete = fields.Boolean(default=False, readonly=True)
    main_rec_id = fields.Integer(index=True, string="Main Record ID", readonly=True)

    # job = type("Priority", (), {"eta": 1})

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            main_rec_id = 'main_rec_id' in vals
            # if any rec.no_delete is True: log start replication
            # upload_data() has: rec.main_rec_id = xmlrpc_rec_id
            if rec.no_delete and not main_rec_id:
                _logger.info(f"Start Replication for {self._name}")
                id_key = f"{self._name}_{rec.id}"
                curr_job = (
                    rec.delayable(identity_key=id_key)
                    .upload_data()
                )

                curr_job.delay()

        return res

    @api.model
    def create(self, values):
        res = super().create(values)
        if res.no_delete:
            id_key = f"{self._name}_{res.id}"
            res.with_delay(identity_key=id_key).upload_data()
        return res

    def upload_data(self):
        """Uploads the current record(s) to the main server.
           If an error occurs during upload, a log record is created.
        """
        model_name = self._name

        if REPL_DB == 0:
            raise UserError(_("repl_db is not configured in odoo.conf file"))
        try:
            conn = OdooConnectionSingleton(self.env)

            self.env.cr.execute(f"""
                            SELECT name, ttype,relation FROM ir_model_fields 
                            WHERE model=%s 
                            AND (store=true AND ttype NOT IN ('binary','many2many')) 
                            AND name not in 
                            ('last_update_date',
                            'message_main_attachment_id')
                        """, (model_name,))

            fields_for_repl_rows = self.env.cr.fetchall()
            main_server_flds_dict = conn.execute_kw(self._name, 'fields_get', [], {'attributes': ['type']})

            # get common fields between main_server and repl_server and target only for replication
            common_flds_main__repldb = set(row[0] for row in fields_for_repl_rows) & set(main_server_flds_dict)
            fields_for_repl_rows = [row for row in fields_for_repl_rows if row[0] in common_flds_main__repldb]

            normal_fields = {row[0] for row in fields_for_repl_rows if row[1] not in {'one2many', 'many2one'}}
            m2o_fields = {row[0] for row in fields_for_repl_rows if row[1] == 'many2one'}

            # o2m_fields = {row[0] for row in fields_for_repl_rows if row[1] == 'one2many'}

            # Process each record in self (the current recordset)
            for record in self:
                if not record.no_delete:
                    continue

                # Prepare data to upload (you might want to customize the read fields)
                all_data = record.read()[0]
                all_data.pop('no_delete', None)
                all_data.pop('main_rec_id', None)
                data = {k: v for k, v in all_data.items() if k in normal_fields}
                data.update({k: record._get_m2o_val(k) for k, v in all_data.items() if k in m2o_fields})

                data.update(repl_id=record.id, repl_db=REPL_DB)
                data.update(repl_create_date=record.create_date, repl_write_date=record.write_date)

                # Check if the record already exists on the main server.
                main_rec_id = record.main_rec_id
                if not main_rec_id:
                    remote_ids = conn.execute_kw(
                        self._name, 'search',
                        [[('repl_id', '=', record.id), ('repl_db', '=', REPL_DB)]]
                    )
                    main_rec_id = remote_ids and remote_ids[0]

                if main_rec_id:
                    # Update existing record on main server
                    conn.execute_kw(
                        self._name, 'write', [[main_rec_id], data]
                    )
                    _logger.info("Updated record %s on main server for model %s", record.id, self._name)

                else:
                    # Create new record on main server
                    main_rec_id = conn.execute_kw(
                        self._name, 'create', [data]
                    )
                    record.sudo().main_rec_id = main_rec_id
                    _logger.info("Created record %s on main server for model %s", record.id, self._name)
        except RetryableJobError as e:
            raise e
        except Exception as e:
            raise RetryableJobError(repr(e))

    def _get_m2o_val(self, m2o_name):
        m2o_rec = getattr(self, m2o_name)
        if hasattr(m2o_rec, 'main_rec_id'):
            m2o_val = m2o_rec.main_rec_id
            if not m2o_val:
                raise RetryableJobError(f"Still {m2o_rec}.main_rec_id=0", seconds=5)

        else:
            m2o_val = m2o_rec.id
        return m2o_val
