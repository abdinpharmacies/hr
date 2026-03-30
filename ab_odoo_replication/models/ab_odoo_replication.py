# -*- coding: utf-8 -*-
import datetime
import math
import re
from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.tools import config
from odoo.addons.ab_odoo_connect import OdooConnectionSingleton
import logging
from typing import List, Dict
from psycopg2.errors import ForeignKeyViolation

_logger = logging.getLogger(__name__)


# -------------------------------
# Helper: parse FK violation text
# -------------------------------
def _parse_missing_fk(error_msg):
    """
    Parse messages like:
    'Key (product_id)=(90062) is not present in table "ab_product".'
    Returns (missing_id:int, table_name:str) or (None, None)
    """
    pattern = r'\((\d+)\)\s+is not present in table "([^"]+)"'
    m = re.search(pattern, error_msg)
    if not m:
        return None, None

    missing_id_str, table_name = m.groups()
    try:
        missing_id = int(missing_id_str)
    except ValueError:
        return None, None

    return missing_id, table_name


class OdooReplication(models.AbstractModel):
    _name = 'ab_odoo_replication'
    _description = 'ab_odoo_replication'

    _group_xml_ids = []

    class ReplShare:
        model_name = ""
        table_name = ""
        conn = None  # type: OdooConnectionSingleton
        has_main_rec_id = False
        missing_many2one_flds = None  # type: list
        fld__type_rel_dict = None  # type: dict

    def eval_val(self, fld, val, rec_id):
        fld__type_rel_dict = self.ReplShare.fld__type_rel_dict
        ttype = fld__type_rel_dict[fld][0]
        rel_model = fld__type_rel_dict[fld][1]  # None if not relation field (not many2one)
        if type(val) == list and ttype == 'many2one':
            m2o_rec_id = val and val[0]
            if m2o_rec_id:
                m2o_mo = self.env[rel_model]
                if hasattr(m2o_mo, 'main_rec_id'):
                    m2o_rec = m2o_mo.with_context(active_test=False).search([
                        ('main_rec_id', '=', m2o_rec_id)
                    ], limit=1)
                else:
                    m2o_rec = m2o_mo.with_context(active_test=False).search([
                        ('id', '=', m2o_rec_id)
                    ])
                if m2o_rec:
                    return m2o_rec.id
                else:
                    self.ReplShare.missing_many2one_flds.append((rel_model, fld, m2o_rec_id, rec_id))
                    return None
            else:
                return None
        elif not ttype == 'boolean' and not val:
            return None
        else:
            return val

    def _fix_users_and_partners_write_date(self):
        if self.env['res.users'].sudo().with_context(active_test=False).search([('write_date', '>', '1999-01-01')]):
            self.env.cr.execute("""
                                UPDATE res_users
                                set write_date='1999-01-01'
                                where write_date != '1999-01-01';
                                UPDATE res_partner
                                set write_date='1999-01-01'
                                where write_date != '1999-01-01';
                                """)
            self.env.cr.commit()

    def replicate_model(self, model_name: str, limit=10000, commit=True, extra_fields=None,
                        replicate_all=False, extra_domain=None):

        RepLog = self.env['ab_odoo_replication_log'].sudo()
        # conn now
        conn = OdooConnectionSingleton(self.env)
        table_name = model_name.replace('.', '_')
        has_main_rec_id = hasattr(self.env[model_name], 'main_rec_id')

        # initiate ReplShare attributes
        self.ReplShare.conn = conn
        self.ReplShare.model_name = model_name
        self.ReplShare.table_name = table_name
        self.ReplShare.has_main_rec_id = has_main_rec_id
        self.ReplShare.missing_many2one_flds = []

        # fix write_date for base users/partners
        # self._fix_users_and_partners_write_date()

        extra_fields = extra_fields or {}

        remotedb_flds_set = self._get_remotedb_flds_set()
        use_write_date = 'write_date' in remotedb_flds_set
        use_id_pagination = replicate_all or not use_write_date

        # Base domain (حسب آخر write_date + extra_domain)
        base_domain = self._get_target_rpc_domain(replicate_all, extra_domain, use_write_date=use_write_date)

        # تقريب لعدد الأجزاء – استخدامه فقط في الـ log
        server_updates_count = self._get_server_updates_count(base_domain)
        if not server_updates_count:
            return

        parts = math.ceil(server_updates_count / float(limit)) if limit else 1

        # used for many2many groups_id
        if model_name == 'res.users' and extra_fields and (
                'groups_id' in extra_fields or 'group_ids' in extra_fields):
            # refresh group cache per run
            self._group_xml_ids.clear()
            group_xml_ids = self.get_matching_xml_gid_list()
            self._group_xml_ids.extend(group_xml_ids)

        # تجهيز الفيلدز المشتركة بين repldb و remotedb
        repldb_flds__name_type_rel = self._get_repldb_flds__name_type_rel()
        repldb_flds_set = {row[0] for row in repldb_flds__name_type_rel}
        # get shared - intersection - fields between repldb and remotedb
        pagination_fields = {'id'}
        if use_write_date:
            pagination_fields.add('write_date')
        fields_to_get = list((repldb_flds_set & remotedb_flds_set) | extra_fields.keys() | pagination_fields)

        self.ReplShare.fld__type_rel_dict = {
            row[0]: (row[1], row[2])
            for row in repldb_flds__name_type_rel
            if row[0] in fields_to_get
        }

        # 🔑 مفاتيح الـ seek pagination
        # نبدأ من آخر نقطة تكرار محفوظة في جدول الـ log (لو متاحة)
        if replicate_all:
            last_write_date = None
            last_id = 0
        else:
            cursor = RepLog.search(
                [('model_name', '=', model_name)],
                limit=1
            )
            if cursor and cursor.last_write_date:
                last_write_date = cursor.last_write_date
                last_id = cursor.last_id or 0
            else:
                last_write_date = None
                last_id = 0

        order_by = 'id' if use_id_pagination else 'write_date, id'

        processed = 0
        part = 0

        init_server_updates = [0]
        while True:
            # Build incremental domain based on آخر record اتعمله replicate في الـ run ده
            if use_id_pagination:
                if last_id:
                    domain = fields.Domain.AND([base_domain, [('id', '>', last_id)]])
                    domain = list(domain)
                else:
                    domain = base_domain
            else:
                if last_write_date is None:
                    domain = base_domain
                else:
                    incr_domain = [
                        '|',
                        ('write_date', '>', last_write_date),
                        '&', ('write_date', '=', last_write_date),
                        ('id', '>', last_id),
                    ]
                    domain = fields.Domain.AND([base_domain, incr_domain])
                    domain = list(domain)
            # مفيش offset خالص – دايمًا 0
            server_updates = self._get_server_updates(domain, fields_to_get, limit, order_by)

            if not server_updates:
                break  # مفيش records كمان بنفس الشروط
            if part > (parts + 1):
                _logger.warning("Parts exceeded + 1")
                break

            init_server_updates = server_updates

            part += 1
            msg = f'### Replicating {model_name} Part {part}/{parts}'

            for rec in server_updates:  # type: dict
                # Skip admin and other built-in users
                if model_name == 'res.users' and rec.get('id') <= 5:
                    continue
                if model_name == 'res.partner' and rec.get('id') <= 6:
                    continue

                processed += 1
                if processed % 100 == 0:
                    if model_name == 'res.users':
                        self.env.cr.commit()
                    _logger.info(f"{msg} , --- record {processed}/{server_updates_count}")

                self._replicate_main_fields(rec)

                if model_name == 'res.users':
                    self._replicate_password(rec)

                self._replicate_extra_fields(extra_fields, rec)

            # commit batch لو طلبت
            if commit:
                # تحديث آخر write_date و id طبقًا لآخر record في الـ batch
                last = server_updates[-1]
                last_write_date = last.get('write_date')
                last_id = last.get('id', 0)
                self._update_replication_cursor(model_name, last_write_date, last_id)
                self.env.cr.commit()

            # تحديث آخر write_date و id طبقًا لآخر record في الـ batch
            last = server_updates[-1]
            last_write_date = last.get('write_date')
            last_id = last.get('id', 0)

        # بعد ما نخلص كل الـ batches
        self._replicate_missing_many2one()

        # 🔄 تحديث كيرسور التكرار بعد انتهاء كل الـ batches
        if last_write_date:
            self._update_replication_cursor(model_name, last_write_date, last_id)

    def _get_remotedb_flds_set(self):
        conn = self.ReplShare.conn
        model_name = self.ReplShare.model_name
        fields_info = conn.execute_kw(
            model_name, 'fields_get',
            [],
            {'attributes': ['type']}
        )

        return set(fields_info.keys())

    @api.model
    def _update_replication_cursor(self, model_name, last_write_date, last_id):
        """Update or create replication cursor for the given model."""
        if not last_write_date:
            return  # Nothing to update

        RepLog = self.env['ab_odoo_replication_log'].sudo()

        cursor = RepLog.search([('model_name', '=', model_name)], limit=1)
        vals = {
            'last_write_date': last_write_date,
            'last_id': last_id,
            'last_run': fields.Datetime.now(),
        }

        if cursor:
            cursor.write(vals)
        else:
            vals['model_name'] = model_name
            RepLog.create(vals)

    def _get_server_updates_count(self, domain):
        conn = self.ReplShare.conn
        model_name = self.ReplShare.model_name

        return conn.execute_kw(
            model_name, 'search_count',
            [domain],
            {
                'context': {'active_test': False}  # Include non-active records
            }
        )

    def _replicate_password(self, rec):
        conn = self.ReplShare.conn
        user_id = rec.get('id', 0)
        try:
            if user_id <= 6:
                return
            encrypted_password = conn.execute_kw(
                'res.users', 'get_encrypted_password',
                [user_id, config.get('xmlrpc_pass')]
            )
        except Exception as ex:
            raise UserError(repr(ex))

        if encrypted_password:
            user = self.env['res.users'].sudo().browse(user_id)
            if user.password != encrypted_password:
                self.env.cr.execute("UPDATE res_users set password = %s WHERE id = %s",
                                    (encrypted_password, user_id))

    def _get_server_updates(self, domain, fields_to_get, limit, order_by='write_date, id') -> List[Dict]:
        conn = self.ReplShare.conn
        model_name = self.ReplShare.model_name

        return conn.execute_kw(
            model_name, 'search_read',
            [domain],
            {
                'fields': fields_to_get,
                'order': order_by,
                'limit': limit,
                'context': {'active_test': False}  # Include non-active records
            }
        )

    def _get_target_rpc_domain(self, replicate_all=False, extra_domain=None, use_write_date=True):
        model_name = self.ReplShare.model_name
        extra_domain = extra_domain or []

        already_replicated_ids = []
        if model_name == 'res.users':
            already_replicated_ids.extend(range(1, 6))
        if model_name == 'res.partner':
            already_replicated_ids.extend(range(1, 7))

        domain = [
            ('id', 'not in', already_replicated_ids),
        ] + extra_domain

        if use_write_date:
            if replicate_all:
                # start from very old date
                max_write_date = datetime.datetime(year=1999, month=1, day=1, hour=0, minute=0, second=0)
            else:
                # use saved cursor if exists
                cursor = self.env['ab_odoo_replication_log'].sudo().search(
                    [('model_name', '=', model_name)],
                    limit=1
                )
                if cursor and cursor.last_write_date:
                    max_write_date = cursor.last_write_date
                else:
                    max_write_date = datetime.datetime(year=1999, month=1, day=1, hour=0, minute=0, second=0)

            domain = [
                ('write_date', '>=', max_write_date),
            ] + domain

        return domain

    def _get_repldb_flds__name_type_rel(self):
        model_name = self.ReplShare.model_name

        # get fields to replicate
        self.env.cr.execute(f"""
                        SELECT name, ttype,relation FROM ir_model_fields 
                        WHERE model=%s 
                        AND (store=true AND ttype NOT IN ('binary','many2many','one2many')) 
                        AND name not in 
                        ('last_update_date',
                        'message_main_attachment_id')
                    """, (model_name,))
        return self.env.cr.fetchall()

    def _replicate_main_fields(self, rec):
        """
            Replicates main fields from a remote record to the local database, handling plain fields
            and many2one relationships.

            @param rec: Record data as received from the remote database. This includes all fields,
                        including many2one fields.
            @type rec: dict

            @return: None
        """
        model_name = self.ReplShare.model_name
        table_name = self.ReplShare.table_name
        has_main_rec_id = self.ReplShare.has_main_rec_id
        rec_id = rec.get('id', 0)

        rec = {fld: self.eval_val(fld, val, rec_id) for fld, val in rec.items()
               if fld in self.ReplShare.fld__type_rel_dict and fld not in {'create_uid', 'write_uid'}
               }
        model = self.env[model_name].sudo()
        domain = [('main_rec_id', '=', rec.get('id', 0))] if has_main_rec_id else [('id', '=', rec.get('id', 0))]
        existing_rec = model.with_context(active_test=False).search(domain)

        # if fld_name != 'id' to remove id from update_str sql
        update_str = ','.join(f"{fld_name}=%s" for fld_name in rec if fld_name != 'id')

        insert_str = ','.join(k for k in rec)
        vals_tuple = tuple(val for val in rec.values())

        # update is the same for both has_main_rec_id and exact_copy models
        if existing_rec:
            # remove fetched server id from values
            vals_tuple = vals_tuple[1:]
            sql = f"""UPDATE {table_name}
                      SET {update_str}
                      WHERE id=%s"""
            self.env.cr.execute(sql, vals_tuple + (existing_rec.id,))
        # create for has_main_rec_id
        elif has_main_rec_id:
            rec.update({"main_rec_id": rec['id']})
            res = model.create(rec)
            create_date = rec.get('create_date')
            write_date = rec.get('write_date')
            create_uid = False  # rec.get('create_uid')
            write_uid = False  # rec.get('write_uid')
            sql = f"""UPDATE {table_name}
                      SET create_date=%s, write_date=%s, create_uid=%s, write_uid=%s
                      WHERE id=%s"""
            self.env.cr.execute(sql, (create_date, write_date, create_uid, write_uid, res.id,))

        # create for exact_copy models
        else:
            sql = f"""
               INSERT INTO {table_name}({insert_str})
               VALUES ({','.join(['%s'] * len(rec))})"""
            self.env.cr.execute(sql, vals_tuple)

    def _replicate_extra_fields(self, extra_fields, rec):
        for fld, ttype in extra_fields.items():
            if ttype == 'binary':
                self._replicate_binary_field(fld, rec)
            elif ttype == 'many2many':
                self._replicate_many2many_field(fld, rec)

    def _replicate_binary_field(self, fld, rec):
        model_name = self.ReplShare.model_name

        rec_id = rec.get('id', 0)
        datas = rec.get(fld)
        if datas:
            attachment_mo = self.env['ir.attachment'].sudo()
            att = attachment_mo.search([
                ('res_field', '=', fld),
                ('res_model', '=', model_name),
                ('res_id', '=', rec_id),
            ])

            if att:
                att.write({'datas': datas})
            else:
                # Create an attachment in Odoo, storing the binary PDF data
                self.env['ir.attachment'].create({
                    'name': fld,
                    'type': 'binary',
                    'datas': datas,
                    'res_model': model_name,
                    'res_field': fld,
                    'res_id': rec_id,
                })

    def _filter_existing_ids(self, model_name, ids_list):
        """
        Return only IDs that actually exist in the given model.
        """
        if not ids_list:
            return []

        model = self.env[model_name].with_context(active_test=False).sudo()
        existing = model.search([('id', 'in', ids_list)])
        return existing.ids

    def _replicate_many2many_field(self, fld, rec):
        try:
            model_name = self.ReplShare.model_name

            self = self.with_context(replication=True)
            model = self.env[model_name].with_context(active_test=False).sudo()
            rec_id = rec.get('id', 0)
            other_ids = rec.get(fld)

            if model_name == 'res.users' and fld in ('groups_id', 'group_ids'):
                if rec_id > 5:
                    # {group['module']}.{group['name']} --> base.group_user, ab_hr.group_basic_data, ... etc
                    other_xml_ids = [self.env.ref(f"{group['module']}.{group['name']}").id
                                     for group in self._group_xml_ids
                                     if group['res_id'] in other_ids]

                    # todo: do group remove if the 'replica group' match 'main group'
                    if fld == 'groups_id':
                        model.search([('id', '=', rec_id)]).write({'group_ids': [(4, gid) for gid in other_xml_ids]})
                    if fld == 'group_ids':
                        model.search([('id', '=', rec_id)]).write({'group_ids': [(6, 0, other_xml_ids)]})

            else:
                related_model = model._fields[fld].comodel_name

                # Filter only existing IDs
                safe_ids = self._filter_existing_ids(related_model, other_ids)

                if len(safe_ids) != len(other_ids):
                    missing = set(other_ids) - set(safe_ids)
                    self.replicate_model(related_model, replicate_all=True, extra_domain=[('id', 'in', list(missing))])

                # Write safely without FK errors
                model.browse(rec_id).write({fld: [(6, 0, other_ids)]})

        except ForeignKeyViolation as e:
            msg = str(e)
            missing_id, table_name = _parse_missing_fk(msg)
            msg += f"\n\n{table_name}: {missing_id}"
            raise UserError(msg)

    def _replicate_missing_many2one(self):
        model_name = self.ReplShare.model_name
        table_name = self.ReplShare.table_name

        """
        self.ReplShare.missing_many2one_flds is a list of tuples:
        [(missing_model, missing_field, many2one_rec_id, rec_id)]
          missing: means not replicated
          missing_model: refers to many2one model
          missing_field: refers to many2one field
          many2one_rec_id: many2one field value (e.g account_id=23)
          rec_id: record id that has many2one field (e.g ab_accounting_je_line(1000))
        """

        # internal means 'many2one model' is same as 'target replicated model' (e.g parent_id)
        # if internal, then replicate immediately
        internal_many2one_flds = [(item[1], item[2], item[3])
                                  for item in self.ReplShare.missing_many2one_flds
                                  if item[0] == model_name]
        # external means 'many2one model' is another model
        # if external, then this means we need to replicate entire many2one model (e.g Wrong Replication Order)
        external_many2one_flds = [(item[1], item[2], item[3], item[0])
                                  for item in self.ReplShare.missing_many2one_flds
                                  if item[0] != model_name]
        # Replicating Internal Many2one fields
        for many2one_name, many2one_value, rec_id in internal_many2one_flds:
            if many2one_name in {'create_uid', 'write_uid'}:
                continue
            self.env.cr.execute(f"""UPDATE {table_name} SET {many2one_name} = %s WHERE id = %s
                """, (many2one_value, rec_id))
        self.env.cr.execute(f"""SELECT setval ('{table_name}_id_seq', (SELECT MAX (id) FROM {table_name})+1);""")

        self.env.cr.commit()

        # Getting external not replicated many2one models.
        missing_models = {item[0] for item in self.ReplShare.missing_many2one_flds if item[0] != model_name}

        # Replicate external not replicated many2one models manually
        #  to make many2one record id available (existed)
        for mo in missing_models:
            self.replicate_model(mo)

        # Now we can update external many2one field, after many2one model was replicated.
        for many2one_name, many2one_value, rec_id, m2o_model_name in external_many2one_flds:
            model = self.env[m2o_model_name].sudo()
            if hasattr(model, 'main_rec_id'):
                rec = model.with_context(active_test=False).search([('main_rec_id', '=', rec_id)], limit=1)
                rec_id = rec.id

            Many2oneFld = model._fields.get(many2one_name)
            if Many2oneFld:
                related_model = Many2oneFld.comodel_name

                # Filter only existing IDs
                safe_ids = self._filter_existing_ids(related_model, [many2one_value])

                if many2one_value not in safe_ids:
                    self.replicate_model(related_model, replicate_all=True,
                                         extra_domain=[('id', 'in', [many2one_value])])

            self.env.cr.execute(f"""UPDATE {table_name} SET {many2one_name} = %s where id=%s
                """, (many2one_value, rec_id))

    def init(self):
        self.env.cr.execute("""
                            UPDATE res_partner
                            set write_date='2000-01-01'
                            WHERE id <= 6;
                            UPDATE res_users
                            set write_date='2000-01-01'
                            WHERE id <= 5;
                            """)

        lang_model = self.env['res.lang'].sudo()
        language = lang_model.search([('code', '=', 'ar_001')], limit=1)

        if not language:
            # Activate existing language if available, otherwise create it.
            language = lang_model._activate_lang('ar_001')

        if language:
            language.write({'active': True})

    def add_res_company_rel_for_all_users(self):
        cr = self.env.cr
        users = self.env['res.users'].sudo().with_context(active_test=False).search([])
        cr.execute("select user_id from res_company_users_rel")

        already_added_ids = {row[0] for row in cr.fetchall()}
        for user in users:
            if user.id not in already_added_ids:
                try:
                    cr.execute(f"""
                    insert into res_company_users_rel(cid,user_id)
                    VALUES (1,{user.id}) 
                    """)
                except Exception as ex:
                    _logger.warning(f'already created for this user{user.id}')

        cr.commit()

    def get_matching_xml_gid_list(self):
        """
        Get a list of ir.model.data records (from the remote server)
        that correspond to the groups existing on the replica.

        Returns a list of dicts: [{'module': ..., 'name': ..., 'res_id': ...}, ...]
        """
        conn = self.ReplShare.conn

        # 1) Get all groups in the replica and their xml_ids
        groups = self.env['res.groups'].with_context(active_test=False).search([])
        if not groups:
            return []

        local_xml_ids = self.env['ir.model.data'].with_context(active_test=False).search([
            ('res_id', 'in', groups.ids),
            ('model', '=', 'res.groups'),
        ])

        if not local_xml_ids:
            return []

        # Build a set of (module, name) pairs that we actually care about
        local_pairs = {(rec.module, rec.name) for rec in local_xml_ids}

        # 2) Read remote ir.model.data for res.groups in batches
        remote_domain = [('model', '=', 'res.groups')]
        fields_to_read = ['module', 'name', 'res_id']
        limit = 1000
        offset = 0

        matched = []

        while True:
            batch = conn.execute_kw(
                'ir.model.data', 'search_read',
                [remote_domain],
                {
                    'fields': fields_to_read,
                    'order': 'id',
                    'offset': offset,
                    'limit': limit,
                    'context': {'active_test': False},
                }
            )

            if not batch:
                break

            # Keep only records whose (module, name) exist locally
            for rec in batch:
                if (rec.get('module'), rec.get('name')) in local_pairs:
                    matched.append(rec)

            offset += limit

        return matched

    # def send_message_repl_channel(self):
    #     # 1. Get the "General" channel
    #     repl_channel = self.env.ref('ab_odoo_replication.ab_odoo_replication_channel')
    #
    #     # 3. Post the message to the channel
    #     repl_channel.message_post(
    #         body="<b>📢 Internal Notification:</b> New policy update is available.",
    #         message_type="comment",
    #         subtype_xmlid="mail.mt_comment",
    #         author_id=self.env.user.partner_id.id
    #     )
