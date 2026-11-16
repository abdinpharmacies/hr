"""Private, idempotent security migration; never exposed as a model/RPC method."""
import logging

from .tools.security_roles import LEGACY_ROLES, PARTICIPANT

_logger = logging.getLogger(__name__)
PREFIX = 'ab_supplier_claim_cycle.'
LEGACY_ACCESS = tuple(
    prefix + department
    for department in ('inventory', 'purchasing', 'supplier_accounts', 'bank_accounts', 'tax')
    for prefix in ('claim_', 'history_', 'ab_costcenter_', 'document_')
)
LEGACY_RULES = tuple(
    prefix + department
    for department in ('inventory', 'purchasing', 'supplier_accounts', 'bank_accounts', 'tax')
    for prefix in ('claim_read_', 'history_read_', 'claim_write_')
) + ('document_department_submitted', 'stage_state_department_submitted')


def consolidate_department_groups(env):
    from odoo import Command, fields
    from odoo.exceptions import UserError

    def references(model, names):
        records = env[model]
        for name in names:
            record = env.ref(PREFIX + name, raise_if_not_found=False)
            if record:
                records |= record
        return records.exists()

    groups = references('res.groups', LEGACY_ROLES)
    if not groups:
        _logger.info('Supplier claim role cleanup already complete')
        return {'groups_removed': 0, 'users_preserved': 0}
    participant = env.ref(PREFIX + PARTICIPANT)
    accesses = env['ir.model.access'].search([('group_id', 'in', groups.ids)])
    rules = env['ir.rule'].search([('groups', 'in', groups.ids)])
    expected_access = references('ir.model.access', LEGACY_ACCESS)
    expected_rules = references('ir.rule', LEGACY_RULES)
    dependencies = []
    if accesses - expected_access:
        dependencies.append('custom access controls')
    if rules - expected_rules or rules.mapped('groups') - groups:
        dependencies.append('custom or shared record rules')
    if groups.mapped('menu_access') or groups.mapped('view_access'):
        dependencies.append('menu/view group restrictions')
    if groups.mapped('implied_by_ids') - groups:
        dependencies.append('other groups implying department groups')
    if groups.mapped('implied_ids') - groups - participant:
        dependencies.append('additional permissions implied by department groups')
    view_domain = fields.Domain.OR([
        fields.Domain('arch_db', 'ilike', PREFIX + name) for name in LEGACY_ROLES
    ])
    if env['ir.ui.view'].with_context(active_test=False).search_count(view_domain):
        dependencies.append('view XML referring to department groups')
    if dependencies:
        raise UserError('Supplier claim role cleanup stopped: %s. Resolve these dependencies before upgrading.' % ', '.join(dependencies))

    # Materialize effective membership before deleting groups and their implied links.
    users = groups.with_context(active_test=False).mapped('all_user_ids')
    users.write({'group_ids': [Command.link(participant.id)]})
    group_count, user_count = len(groups), len(users)
    access_count, rule_count = len(accesses), len(rules)
    # Delete rules first: an empty group list would otherwise turn a rule global.
    rules.unlink()
    accesses.unlink()
    groups.unlink()
    env.invalidate_all()
    if any(participant not in user.all_group_ids for user in users):
        raise UserError('Supplier claim role cleanup lost a user membership.')
    result = {'groups_removed': group_count, 'users_preserved': user_count,
              'access_controls_removed': access_count, 'record_rules_removed': rule_count}
    _logger.info('Supplier claim role cleanup: %s', result)
    return result
