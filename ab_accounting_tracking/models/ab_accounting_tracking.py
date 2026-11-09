import json

from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import re


class AccountingTracking(models.Model):
    _name = 'ab_accounting_tracking'
    _description = 'ab_accounting_tracking'
    _rec_name = 'je_line_id'
    _order = 'create_date desc'
    je_line = fields.Integer(index=True)
    je_line_id = fields.Many2one('ab_accounting_je_line', compute='_compute_je_line_id', compute_sudo=True)
    field_diff_json = fields.Text(string="Field Changes (JSON)", default="{}")
    field_diff_html = fields.Html(string="Change Summary", compute="_compute_field_diff_html")
    has_differences = fields.Boolean(compute='_compute_has_differences')

    # created_by_id = fields.Many2one('res.users', related='je_line_id.create_uid')
    update_counter = fields.Integer()

    @api.depends('field_diff_json')
    def _compute_field_diff_html(self):
        for rec in self:
            try:
                diffs = json.loads(rec.field_diff_json or '{}')
                user_changes = {}

                # Group changes by user
                for field, changes in diffs.items():
                    for change in changes:
                        user = change.get('user_name', 'Unknown')
                        user_changes.setdefault(user, []).append({
                            'field': field,
                            'old': change.get('old', ''),
                            'new': change.get('new', '')
                        })

                # Build HTML
                sections = []
                for user, changes in user_changes.items():
                    lines = []
                    for c in changes:
                        old_val = c['old'] or '—'
                        new_val = c['new'] or '—'
                        # Determine arrow direction based on old_val
                        arrow = '→' if re.match(r'^[a-zA-Z0-9]', old_val) else '←'
                        lines.append(
                            f"<li><b>{c['field']}</b>: "
                            f"<span style='color:#c00'>{old_val}</span> {arrow} "
                            f"<span style='color:green'>{new_val}</span></li>"
                        )

                    section_html = f"<p><b style='color:#333'>Edited by: {user}</b></p><ul>{''.join(lines)}</ul>"
                    sections.append(section_html)

                rec.field_diff_html = Markup(''.join(sections))

            except Exception:
                rec.field_diff_html = "<i style='color:gray'>Invalid change data</i>"

    @api.depends('field_diff_json')
    def _compute_has_differences(self):
        for rec in self:
            rec.has_differences = False  # default

            try:
                diffs = json.loads(rec.field_diff_json or '{}')
                for changes in diffs.values():
                    if not changes:
                        continue
                    first_old = changes[0].get('old', '')
                    last_new = changes[-1].get('new', '')
                    if str(first_old) != str(last_new):
                        rec.has_differences = True
                        break  # no need to check more fields
            except Exception:
                rec.has_differences = False

    def _compute_je_line_id(self):
        for rec in self:
            rec.je_line_id = self.env['ab_accounting_je_line'].sudo().browse(rec.je_line).id
