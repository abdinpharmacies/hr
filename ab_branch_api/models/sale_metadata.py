"""Technical source snapshots; never operational branch record identifiers."""
from contextvars import ContextVar
from datetime import date, datetime
import math
import re
from uuid import UUID

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


_metadata_write = ContextVar('branch_sale_metadata_write', default=None)
_SCALAR_TYPES = {'boolean', 'char', 'text', 'selection', 'integer', 'float', 'monetary', 'date', 'datetime'}


class SaleMetadata(models.AbstractModel):
    _name = 'ab_branch_sale_metadata'
    _description = 'Technical Sale Metadata'

    metadata = fields.Json(string='Metadata', default=dict, readonly=True, copy=False,
                           groups='base.group_system')

    @api.model_create_multi
    def create(self, vals_list):
        if 'default_metadata' in self.env.context or any('metadata' in vals for vals in vals_list):
            raise AccessError(_('Sale metadata is server-managed.'))
        return super().create(vals_list)

    def write(self, vals):
        scope = _metadata_write.get()
        if 'metadata' in vals and not (scope and scope[:3] == (self.env.cr, self._name, tuple(self.ids))
                                       and vals is scope[3]):
            raise AccessError(_('Sale metadata is server-managed.'))
        return super().write(vals)

    def _write_sale_metadata(self, metadata):
        self.ensure_one()
        self.check_access('write')
        values = {'metadata': metadata}
        token = _metadata_write.set((self.env.cr, self._name, tuple(self.ids), values))
        try:
            # Only this technical field is elevated, after ordinary record access.
            return self.sudo().write(values)
        finally:
            _metadata_write.reset(token)


class HeaderMetadata(models.Model):
    _name = 'ab_sales_header'
    _inherit = ['ab_sales_header', 'ab_branch_sale_metadata']


class LineMetadata(models.Model):
    _name = 'ab_sales_line'
    _inherit = ['ab_sales_line', 'ab_branch_sale_metadata']


class BranchMetadata(models.AbstractModel):
    _inherit = 'ab_branch_api'

    def _sale_metadata_context(self, payload):
        if 'metadata_context' not in payload:
            return None
        context = payload['metadata_context']
        if (not isinstance(context, dict)
                or set(context) != {'schema_version', 'source', 'header', 'lines'}
                or type(context['schema_version']) is not int or context['schema_version'] != 1
                or not isinstance(context['header'], dict) or not isinstance(context['lines'], list)
                or len(context['lines']) != len(payload.get('lines', []))
                or any(not isinstance(row, dict) for row in context['lines'])):
            raise UserError(_('Invalid sale metadata context.'))
        try:
            UUID(context['source'])
        except (ValueError, TypeError, AttributeError):
            raise UserError(_('Invalid sale metadata context.')) from None
        return context

    def _validate_sale_descriptor(self, field, value, descriptor):
        error = _('Invalid sale field descriptor.')
        if not isinstance(descriptor, dict):
            raise UserError(error)
        kind = descriptor.get('type')
        if not isinstance(kind, str):
            raise UserError(error)
        if kind in ('many2one', 'many2many'):
            ids = descriptor.get('ids')
            model = descriptor.get('model')
            if (set(descriptor) != {'type', 'model', 'ids'}
                    or not isinstance(model, str) or not re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_.]*', model)
                    or not isinstance(ids, list) or any(type(i) is not int or i <= 0 for i in ids)
                    or len(ids) != len(set(ids)) or (kind == 'many2one' and len(ids) > 1)
                    or (kind == 'many2one' and (bool(ids) != bool(value) or (ids and not isinstance(value, dict))
                                              or (not ids and value is not False and value is not None)))
                    or (kind == 'many2many' and (not isinstance(value, list) or len(value) != len(ids)
                                              or any(not isinstance(ref, dict) for ref in value)))):
                raise UserError(error)
            if field and (field.type != kind or field.comodel_name != model):
                raise UserError(error)
        else:
            if set(descriptor) != {'type'} or kind not in _SCALAR_TYPES or (field and field.type != kind):
                raise UserError(error)
            valid = True
            if kind == 'boolean':
                valid = type(value) is bool
            elif kind == 'integer':
                valid = type(value) is int
            elif kind in ('float', 'monetary'):
                valid = type(value) in (int, float) and math.isfinite(value)
            elif kind in ('char', 'text', 'selection'):
                valid = isinstance(value, str) or value is False or value is None
            elif value is not None:
                try:
                    if not isinstance(value, str):
                        raise ValueError()
                    if kind == 'date':
                        date.fromisoformat(value)
                    else:
                        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
                        if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
                            raise ValueError()
                except (ValueError, TypeError):
                    valid = False
            if not valid:
                raise UserError(error)

    def _sale_values_with_metadata(self, model, source, allowed, context=None, descriptors=None):
        if not isinstance(source, dict):
            raise UserError(_('Invalid sale payload.'))
        for key in source:
            if key not in allowed:
                raise UserError(_('Unsupported sale field: %s') % key)
        if context is not None and (not isinstance(descriptors, dict) or set(descriptors) != set(source)):
            raise UserError(_('Invalid sale field descriptor.'))
        values, missing, relations = {}, {}, {}
        for key, value in source.items():
            field = model._fields.get(key)
            descriptor = descriptors[key] if context is not None else None
            if context is not None:
                self._validate_sale_descriptor(field, value, descriptor)
            if not field:
                if key in {'contract_id', 'total_invoice_discount'} and value:
                    raise UserError(_('Branch module does not support field: %s') % key)
                if context is None:
                    if value:
                        raise UserError(_('Missing source metadata for %s. Correct and resubmit the rejected bill from the updated callcenter.') % key)
                    continue
                if descriptor['type'] in ('many2one', 'many2many'):
                    missing[key] = descriptor['ids']
                    relations[key] = descriptor['model']
                else:
                    missing[key] = value
                continue
            if field.type == 'many2one':
                values[key] = self._resolve(field.comodel_name, value).id if value else False
            elif field.type == 'many2many':
                if not isinstance(value, list):
                    raise UserError(_('Invalid sale field descriptor.'))
                values[key] = [fields.Command.set([self._resolve(field.comodel_name, ref).id for ref in value])]
            elif descriptor and field.type in ('date', 'datetime'):
                values[key] = (datetime.fromisoformat(value.replace('Z', '+00:00')).replace(tzinfo=None)
                               if value and field.type == 'datetime' else value or False)
            else:
                values[key] = value
        metadata = {'schema_version': 1, 'source': context['source'],
                    'relation_models': relations, 'values': missing} if missing else {}
        return values, metadata
