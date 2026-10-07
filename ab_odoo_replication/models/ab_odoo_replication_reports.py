# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.addons.ab_odoo_connect import OdooConnectionSingleton


class OdooReplicationReports(models.AbstractModel):
    _inherit = 'ab_odoo_replication'

    def eval_val(self, fld, val, rec_id):
        """Keep report user identities separate from the shared resolver."""
        ttype, rel_model = self.ReplShare.fld__type_rel_dict[fld]
        if type(val) == list and ttype == 'many2one' and val and val[0]:
            if rel_model == 'res.users':
                return val[0]
            if rel_model == 'ab_users':
                self._ensure_ab_user_ids([val[0]])
                return val[0]
        return super().eval_val(fld, val, rec_id)

    @api.model
    def _ensure_ab_user_ids(self, user_ids):
        """Create missing passive identities without changing existing users."""
        users = self.env['ab_users'].sudo().with_context(active_test=False)
        users.flush_model()
        missing_ids = sorted(set(user_ids) - set(users.browse(user_ids).exists().ids))
        if missing_ids:
            self.env.cr.execute(
                '''
                    INSERT INTO ab_users (id, active)
                    SELECT unnest(%s::integer[]), true
                    ON CONFLICT (id) DO NOTHING
                    RETURNING id
                ''',
                (missing_ids,),
            )
            inserted_ids = [row[0] for row in self.env.cr.fetchall()]
            if inserted_ids:
                self._refresh_force_id_record(
                    users, inserted_ids, changed_fields=['active'], created=True,
                )
                self._sync_force_id_sequence(users)
        return users.browse(user_ids)

    @api.model
    def replicate_ab_users(self, limit=10000, commit=True, replicate_all=False):
        """Copy remote user identities into passive users with the same IDs.

        Remote write_date is used only for pagination and the dedicated cursor.
        Replay the cursor timestamp on subsequent runs to catch updates within
        the same second; unchanged identities are not written again.
        """
        conn = OdooConnectionSingleton(self.env)
        cursor_key = 'replicate_ab_users'
        cursor = self.env['ab_odoo_replication_log'].sudo().search(
            fields.Domain('model_name', '=', cursor_key), limit=1,
        )
        base_domain = fields.Domain.TRUE
        if not replicate_all and cursor.last_write_date:
            base_domain &= fields.Domain(
                'write_date', '>=', fields.Datetime.to_string(cursor.last_write_date),
            )

        domain = base_domain
        while True:
            batch = conn.execute_kw(
                'res.users', 'search_read', [list(domain)],
                {
                    'fields': ['id', 'name', 'login', 'write_date'],
                    'order': 'write_date, id',
                    'limit': limit,
                    'context': {'active_test': False},
                },
            )
            if not batch:
                break

            users = self._ensure_ab_user_ids([row['id'] for row in batch])
            existing = {row['id']: row for row in users.read(['name', 'login'])}
            for row in batch:
                values = {
                    field_name: row[field_name]
                    for field_name in ('name', 'login')
                    if existing[row['id']][field_name] != row[field_name]
                }
                if values:
                    users.browse(row['id']).with_context(replication=True).write(values)

            last = batch[-1]
            self._update_replication_cursor(cursor_key, last['write_date'], last['id'])
            if commit:
                self.env.cr.commit()

            domain = base_domain & (
                fields.Domain('write_date', '>', last['write_date'])
                | (
                    fields.Domain('write_date', '=', last['write_date'])
                    & fields.Domain('id', '>', last['id'])
                )
            )
