from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


WORKFLOW = object()
FINANCIAL = 'ab_inventory_audit.group_manager,ab_inventory_audit.group_financial,base.group_system'


def workflow_context(env):
    return {'lang': env.context.get('lang'), 'tz': env.context.get('tz'),
            'allowed_company_ids': env.companies.ids, '_audit_workflow': WORKFLOW}


def decimal(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError(_('Enter a finite numeric quantity.')) from None
    if not result.is_finite():
        raise ValidationError(_('Enter a finite numeric quantity.'))
    return result


def money(value):
    return decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def unit_factor(product, uom):
    if not uom or uom not in product.uom_ids:
        raise ValidationError(_('Select a configured product unit.'))
    small = decimal(product.unit_s_id.unit_no)
    medium = decimal(product.unit_m_id.unit_no)
    if small <= 0 or (uom.unit_size == 'medium' and medium <= 0):
        raise ValidationError(_('Configure valid unit conversions.'))
    return {'large': small, 'medium': small / (medium or 1), 'small': Decimal(1)}[uom.unit_size]


def count_quantity(product, large=0, medium=0, small=0):
    total = Decimal(0)
    for value, uom in ((large, product.unit_l_id), (medium, product.unit_m_id),
                       (small, product.unit_s_id)):
        amount = decimal(value)
        if amount < 0:
            raise ValidationError(_('Count quantities must be nonnegative.'))
        if amount:
            total += amount * unit_factor(product, uom)
    if total != total.to_integral_value() or total > 2147483647:
        raise ValidationError(_('Quantity must convert exactly to whole smallest units.'))
    return int(total)


def allocate(quantity, weights):
    total = sum(weights.values())
    if not total:
        raise ValidationError(_('Select a source explicitly for a zero-reference surplus.'))
    raw = {key: Decimal(abs(quantity)) * value / total for key, value in weights.items()}
    result = {key: int(value) for key, value in raw.items()}
    remainder = abs(quantity) - sum(result.values())
    for key in sorted(raw, key=lambda key: (-(raw[key] - result[key]), key))[:remainder]:
        result[key] += 1
    return {key: value * (-1 if quantity < 0 else 1) for key, value in result.items()}


class AuditChild(models.AbstractModel):
    _name = 'ab_inventory_audit_child'
    _description = 'Protected Audit Record'

    audit_id = fields.Many2one('ab_inventory_audit', required=True, index=True, ondelete='restrict')
    store_id = fields.Many2one(related='audit_id.store_id', store=True, index=True)
    company_id = fields.Many2one(related='audit_id.company_id', store=True, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get('_audit_workflow') is not WORKFLOW:
            raise AccessError(_('Use the audit workflow actions.'))
        return super().create(vals_list)

    def write(self, vals):
        if self.env.context.get('_audit_workflow') is not WORKFLOW:
            raise AccessError(_('Use the audit workflow actions.'))
        return super().write(vals)

    def unlink(self):
        raise AccessError(_('Audit history cannot be deleted.'))

    def _edit(self, vals):
        return self.sudo().with_context(workflow_context(self.env)).write(vals)

    @api.model
    def _new(self, vals):
        return self.sudo().with_context(workflow_context(self.env)).create(vals).with_env(self.env)


class AuditEvent(models.Model):
    _name = 'ab_inventory_audit_event'
    _inherit = 'ab_inventory_audit_child'
    _description = 'Audit History'
    _order = 'id desc'
    _rec_name = 'action'

    actor_id = fields.Many2one('res.users', required=True)
    occurred_at = fields.Datetime(required=True, default=fields.Datetime.now)
    action = fields.Char(required=True)
    reason = fields.Text()
    revision = fields.Integer(required=True)

    def write(self, vals):
        raise AccessError(_('Audit history cannot be rewritten.'))
