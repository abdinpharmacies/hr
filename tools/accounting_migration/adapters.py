"""Explicit Odoo 15 -> 19 conversions, shared by validation and import."""
from common import MigrationError

ZERO_ONLY = {'res.partner': {'credit_limit', 'partner_gid'}}
OBSOLETE = {
    'res.company': {
        'base_onboarding_company_state': 'Removed onboarding progress; no business data.',
        'default_chatter_preference': 'Obsolete web client layout preference.',
        'default_sidebar_preference': 'Obsolete web client layout preference.',
    },
    'res.users': {
        'chatter_position': 'Obsolete web client layout preference.',
        'sidebar_type': 'Obsolete web client layout preference.',
    },
}
SUPPORT_MODULES = ['resource', 'auto_logout_idle_user_odoo', 'ab_migration_compat']


def adapted_fields(model):
    return set(OBSOLETE.get(model, {})) | ZERO_ONLY.get(model, set()) | (
        {'mobile'} if model == 'res.partner' else {'user_id'} if model == 'ab_store' else set())


def transform(model, original):
    row = dict(original)
    for field in ZERO_ONLY.get(model, set()):
        if row.get(field) not in (None, False, 0):
            raise MigrationError(f'Nonzero legacy field needs mapping: {model}.{field}:{row.get("id")}')
        row.pop(field, None)
    if model == 'res.partner':
        mobile, phone = row.pop('mobile', None), row.get('phone')
        if mobile:
            if phone and phone != mobile:
                raise MigrationError(f'Conflicting phone/mobile: res.partner:{row.get("id")}')
            row['phone'] = phone or mobile
    for field in OBSOLETE.get(model, {}):
        row.pop(field, None)
    if model == 'ab_store':
        # Validated independently against exported HR departments before any writes.
        row.pop('user_id', None)
    return row


def historical_validation_issues(model, row, units, taxes):
    """Detect legacy values accepted by the existing E-Plus import context.

    Never repair historical prices, unit ratios or invoice numbers by guessing.
    These exceptions are reported and allowed only in an explicit development run.
    """
    import re
    issues = []
    if model == 'ab_purchase_header' and not re.fullmatch(r'[a-zA-Z0-9-]+', row.get('doc_code') or ''):
        issues.append('invoice_number_outside_interactive_entry_format')
    elif model == 'ab_product':
        small, medium, large = (units.get(row.get(field), {}) for field in ('unit_s_id', 'unit_m_id', 'unit_l_id'))
        if small and medium and large:
            s, m = small.get('unit_no', 0), medium.get('unit_no', 0)
            if not m or (s == 1 and m > 1) or not round(s / m, 5).is_integer() or (medium.get('type_id') == large.get('type_id') and m > 1):
                issues.append('legacy_product_unit_ratio')
    elif model == 'ab_product_source':
        net = float(row.get('purchase_price') or 0) * (1 - float(row.get('extra_discount_percentage') or 0) / 100)
        selected = [taxes[i] for i in row.get('_m2m', {}).get('taxes_ids', []) if i in taxes]
        first = sum(net * float(t.get('percentage') or 0) / 100 for t in selected if not t.get('apply_on_total'))
        second = sum((net + first) * float(t.get('percentage') or 0) / 100 for t in selected if t.get('apply_on_total'))
        if float(row.get('price') or 0) < net + first + second:
            issues.append('historical_cost_above_selling_price')
    return issues
