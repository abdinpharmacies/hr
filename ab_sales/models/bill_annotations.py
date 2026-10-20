"""Local annotations are separate from immutable financial and retry data."""
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class BillAnnotation(models.Model):
    _name = 'ab_sales_bill_annotation'
    _description = 'Callcenter Bill Annotation'
    _order = 'create_date, id'

    sale_id = fields.Many2one('ab_sales_header', ondelete='restrict', index=True)
    return_id = fields.Many2one('ab_sales_return_header', ondelete='restrict', index=True)
    body = fields.Text(string='Annotation', required=True)
    author_id = fields.Many2one('res.users', string='Author', required=True, readonly=True,
                               default=lambda self: self.env.user, ondelete='restrict')
    _one_bill = models.Constraint('CHECK ((sale_id IS NULL) <> (return_id IS NULL))',
                                  'An annotation must belong to exactly one bill.')

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for vals in vals_list:
            if bool(vals.get('sale_id')) == bool(vals.get('return_id')):
                raise UserError(_('An annotation must belong to exactly one bill.'))
            model, key = ('ab_sales_header', 'sale_id') if vals.get('sale_id') else ('ab_sales_return_header', 'return_id')
            bill = self.env[model].browse(vals[key]).exists()
            bill.check_access('read')
            if not bill or not bill.is_callcenter_order:
                raise AccessError(_('Select an accessible callcenter bill.'))
            body = str(vals.get('body') or '').strip()
            if not body:
                raise UserError(_('Enter an annotation.'))
            prepared.append({key: bill.id, 'body': body, 'author_id': self.env.uid})
        return super().create(prepared)

    def write(self, vals):
        raise AccessError(_('Annotations cannot be changed or deleted. Add a new annotation.'))

    def unlink(self):
        raise AccessError(_('Annotations cannot be changed or deleted. Add a new annotation.'))


class AnnotationApi(models.TransientModel):
    _inherit = 'ab_sales_ui_api'

    def _bill_annotations(self, header, kind):
        key = 'return_id' if kind == 'return' else 'sale_id'
        rows = self.env['ab_sales_bill_annotation'].search(fields.Domain(key, '=', header.id))
        return [{'id': row.id, 'body': row.body, 'author': row.author_id.display_name,
                 'date': fields.Datetime.to_string(row.create_date)} for row in rows]

    @api.model
    def bill_wizard_details(self, header_id):
        result = super().bill_wizard_details(header_id)
        kind, bill = self._bill_wizard_get_record_from_ref(header_id)
        result['annotations'] = self._bill_annotations(bill, kind)
        return result

    @api.model
    def bill_wizard_add_annotation(self, header_id, body):
        kind, bill = self._bill_wizard_get_record_from_ref(header_id)
        key = 'return_id' if kind == 'return' else 'sale_id'
        self.env['ab_sales_bill_annotation'].create({key: bill.id, 'body': body})
        return self._bill_annotations(bill, kind)

    @api.model
    def bill_wizard_update_notes(self, header_id, notes=''):
        raise UserError(_('Invoice notes are fixed. Add a callcenter annotation instead.'))


class AnnotationAccess(models.Model):
    _inherit = 'res.users'

    def _ab_sales_annotation_domain(self):
        return list((fields.Domain('sale_id.is_callcenter_order', '=', True)
                     & fields.Domain(self._ab_sales_bill_domain('sale_id.')))
                    | (fields.Domain('return_id.is_callcenter_order', '=', True)
                       & fields.Domain(self._ab_sales_bill_domain('return_id.'))))
