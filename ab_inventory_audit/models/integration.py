from odoo import api, fields, models, _
from odoo.exceptions import AccessError

from .common import WORKFLOW


def preserve_audit_movements(records):
    if records:
        raise AccessError(_('Audit inventory history must be preserved.'))


class Inventory(models.Model):
    _inherit = 'ab_inventory'

    model_ref = fields.Selection(selection_add=[('ab_inventory_audit_adjustment', 'Inventory Audit')],
                                 ondelete={'ab_inventory_audit_adjustment': preserve_audit_movements})


class Journal(models.Model):
    _inherit = 'ab_accounting_je_header'

    audit_id = fields.Many2one('ab_inventory_audit', readonly=True, copy=False, ondelete='restrict', index=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if (vals.get('res_header_ref') == 'ab_inventory_audit' or vals.get('audit_id')
                    or self.env.context.get('default_res_header_ref') == 'ab_inventory_audit'
                    or self.env.context.get('default_audit_id')):
                if self.env.context.get('_audit_workflow') is not WORKFLOW:
                    raise AccessError(_('Audit journals can only be created by audit posting.'))
                vals['audit_id'] = vals['res_header_id']
        return super().create(vals_list)

    def write(self, vals):
        if self.env.context.get('_audit_workflow') is not WORKFLOW:
            if self.sudo().filtered('audit_id') or 'audit_id' in vals or vals.get('res_header_ref') == 'ab_inventory_audit':
                raise AccessError(_('Audit journals are immutable. Create a corrective audit.'))
        return super().write(vals)

    def unlink(self):
        if self.sudo().filtered('audit_id'):
            raise AccessError(_('Audit journals cannot be deleted.'))
        return super().unlink()


class JournalLine(models.Model):
    _inherit = 'ab_accounting_je_line'

    @api.model_create_multi
    def create(self, vals_list):
        header_ids = {vals.get('header_id', self.env.context.get('default_header_id')) for vals in vals_list}
        headers = self.env['ab_accounting_je_header'].sudo().browse([value for value in header_ids if value])
        if headers.filtered('audit_id') and self.env.context.get('_audit_workflow') is not WORKFLOW:
            raise AccessError(_('Audit journals are immutable. Create a corrective audit.'))
        return super().create(vals_list)

    def write(self, vals):
        headers = self.sudo().header_id | self.env['ab_accounting_je_header'].sudo().browse(vals.get('header_id', []))
        if headers.filtered('audit_id') and self.env.context.get('_audit_workflow') is not WORKFLOW:
            raise AccessError(_('Audit journals are immutable. Create a corrective audit.'))
        return super().write(vals)

    def unlink(self):
        if self.sudo().header_id.filtered('audit_id'):
            raise AccessError(_('Audit journals cannot be deleted.'))
        return super().unlink()

    def btn_reverse_je(self):
        if self.sudo().header_id.filtered('audit_id'):
            raise AccessError(_('Audit journals are immutable. Create a corrective audit.'))
        return super().btn_reverse_je()


class Source(models.Model):
    _inherit = 'ab_product_source'

    audit_movement_ids = fields.One2many('ab_inventory', 'source_id', groups='ab_inventory_audit.group_financial')
    audit_origin_id = fields.Many2one('ab_inventory_audit', readonly=True, copy=False, ondelete='restrict', index=True)

    @api.model_create_multi
    def create(self, vals_list):
        if (any('audit_origin_id' in vals for vals in vals_list) or self.env.context.get('default_audit_origin_id')) and self.env.context.get('_audit_workflow') is not WORKFLOW:
            raise AccessError(_('Audit source links are maintained by posting.'))
        return super().create(vals_list)

    def write(self, vals):
        if 'audit_origin_id' in vals:
            raise AccessError(_('Audit source links cannot be changed.'))
        observed = {'price', 'exp_date', 'no_expiry', 'purchase_price', 'extra_discount_percentage',
                    'taxes_ids', 'uom_id', 'product_id'}
        if observed.intersection(vals):
            self.check_access('write')
            movements = self.env['ab_inventory'].sudo()._read_group(
                [('source_id', 'in', self.ids)], ['store_id'], [])
            store_ids = {store.id for (store,) in movements}
            store_ids.update(self.sudo().audit_origin_id.store_id.ids)
            audits = self.env['ab_inventory_audit'].sudo().search([
                ('store_id', 'in', sorted(store_ids)), ('state', 'in', ['counting', 'review', 'approved'])])
            audits.store_id.sudo()._lock_stock_scope()
        return super().write(vals)

    def unlink(self):
        if self.sudo().filtered('audit_origin_id'):
            raise AccessError(_('Audit stock sources cannot be deleted.'))
        return super().unlink()


class Attachment(models.Model):
    _inherit = 'ir.attachment'

    def _check_audit_attachment(self, vals=None):
        vals = vals or {}
        targets = [(rec.res_model, rec.res_id, rec.public, rec.access_token) for rec in self.sudo()]
        if vals.get('res_model', '').startswith('ab_inventory_audit'):
            targets.append((vals['res_model'], vals.get('res_id'), vals.get('public'), vals.get('access_token')))
        for model, record_id, public, token in targets:
            if not model or not model.startswith('ab_inventory_audit'):
                continue
            if model not in self.env.registry or not record_id:
                raise AccessError(_('Attach files to an authorized audit record.'))
            record = self.env[model].browse(record_id).exists()
            if not record:
                raise AccessError(_('Attach files to an authorized audit record.'))
            record.check_access('read')
            if public or token or vals.get('public') or vals.get('access_token'):
                raise AccessError(_('Audit attachments cannot be shared publicly.'))
            if vals.get('res_model', model) != model or vals.get('res_id', record_id) != record_id:
                raise AccessError(_('Audit attachments cannot be moved to another record.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._check_audit_attachment(vals)
        with self.env.cr.savepoint():
            records = super().create(vals_list)
            records._check_audit_attachment()
            return records

    def _audit_attachment_immutable(self):
        for attachment in self.sudo():
            if not (attachment.res_model or '').startswith('ab_inventory_audit'):
                continue
            record = self.env[attachment.res_model].browse(attachment.res_id)
            record.check_access('read')
            audit = record if record._name == 'ab_inventory_audit' else record.audit_id if 'audit_id' in record._fields else False
            if audit and audit.state == 'posted':
                raise AccessError(_('Posted audit attachments cannot be changed or deleted.'))

    def write(self, vals):
        self._check_audit_attachment(vals)
        self._audit_attachment_immutable()
        with self.env.cr.savepoint():
            result = super().write(vals)
            self._check_audit_attachment()
            return result

    def unlink(self):
        self._check_audit_attachment()
        self._audit_attachment_immutable()
        return super().unlink()

    def generate_access_token(self):
        if any((rec.res_model or '').startswith('ab_inventory_audit') for rec in self.sudo()):
            raise AccessError(_('Audit attachments cannot be shared publicly.'))
        return super().generate_access_token()
