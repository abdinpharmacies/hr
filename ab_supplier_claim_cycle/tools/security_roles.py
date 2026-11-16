"""Role names accepted in current and historical supplier-claim bundles."""
TARGET_VERSION = '19.0.7.1.0'
PARTICIPANT = 'supplier_claim_group_participant'
CURRENT_ROLES = (
    PARTICIPANT, 'supplier_claim_group_user',
    'supplier_claim_group_reviewer', 'supplier_claim_group_admin',
)
LEGACY_ROLES = tuple('supplier_claim_group_' + department for department in (
    'inventory', 'purchasing', 'supplier_accounts', 'bank_accounts', 'tax',
))


def mapped_role_name(name):
    if name in LEGACY_ROLES:
        return PARTICIPANT
    if name in CURRENT_ROLES:
        return name
    raise ValueError('Unsupported supplier claim role: %s' % name)
