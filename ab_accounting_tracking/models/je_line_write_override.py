import json
from odoo import api, fields, models, _

tracked_fields = {'credit_val': 'float', 'debit_val': 'float', 'store_id': 'many2one', 'due_date': 'datetime',
                  'costcenter_id': 'many2one', 'doc_no': 'str', 'account_id': 'many2one'}


class AccountingJeLine(models.Model):
    _name = 'ab_accounting_je_line'
    _inherit = 'ab_accounting_je_line'

    @api.model_create_multi
    def create(self, vals_list):
        records = self.browse()
        for values in vals_list:
            records |= self._create_one_ab_accounting_tracking_accountingjeline(values)
        return records

    def _create_one_ab_accounting_tracking_accountingjeline(self, values):
        res = super().create(values)
        track_mo = self.env['ab_accounting_tracking'].sudo()
        track_je = track_mo.search([('je_line', '=', res.id)])
        if not track_je and self.env.user.id > 6:
            track_mo.create({
                'je_line': res.id,
                'update_counter': 0,
                'field_diff_json': "{}",
            })
        return res

    def write(self, values):
        track_mo = self.env['ab_accounting_tracking'].sudo()
        tracks = track_mo.search([('je_line', 'in', self.ids)])
        tracks_d = {track.je_line: track for track in tracks}
        user_id = self.env.user.id
        for rec in self:
            # Load existing diff history (if any)
            full_diff = {}

            if not rec.is_posted or user_id <= 6:
                continue
            track = tracks_d.get(rec.id)
            if not track:
                track = track_mo.create({
                    'je_line': rec.id,
                    'update_counter': 0,
                    'field_diff_json': "{}",
                })

            if track and track.field_diff_json:
                try:
                    full_diff = json.loads(track.field_diff_json)
                except Exception:
                    full_diff = {}

            for field, ftype in tracked_fields.items():
                if field not in values:
                    continue

                old_val = rec[field]
                new_val = values[field]

                # Convert values to human-readable strings
                if ftype == 'many2one':
                    old_disp = old_val.name if old_val else ''
                    new_rec = self.env[rec._fields[field].comodel_name].browse(new_val)
                    new_disp = new_rec.display_name if new_rec.exists() else ''
                else:
                    old_disp = str(old_val)
                    new_disp = str(new_val)

                # Append change if it differs
                if old_disp != new_disp:
                    if field not in full_diff:
                        full_diff[field] = []
                    # full_diff[field].append([old_disp, new_disp]) # Old way
                    # New way
                    full_diff[field].append({
                        "old": old_disp,
                        "new": new_disp,
                        "user_id": self.env.uid,
                        "user_name": self.env.user.name,
                    })

            if full_diff:
                track.field_diff_json = json.dumps(full_diff, ensure_ascii=False)
                track.update_counter += 1

        return super().write(values)
