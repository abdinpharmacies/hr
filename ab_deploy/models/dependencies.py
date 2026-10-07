from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class DeployRequestDependency(models.Model):
    _inherit = 'ab_deploy_request'

    dependency_request_id = fields.Many2one(
        'ab_deploy_request', string='Depends On', ondelete='restrict',
        tracking=True, index=True,
        help='Each selected server must succeed or be manually resolved in this request before it can be queued here.')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.dependency_request_id.check_access('read')
        return records

    def write(self, vals):
        if vals.get('dependency_request_id'):
            self.browse(vals['dependency_request_id']).check_access('read')
        return super().write(vals)

    @api.constrains('dependency_request_id')
    def _check_dependency_request(self):
        # Odoo runs constraints in sudo mode. Reference access is checked in
        # create/write; inspect archived and inaccessible ancestors here as well.
        for request in self.sudo():
            seen = set()
            current = request
            while current:
                if current.id in seen:
                    raise ValidationError(_('Deployment dependencies cannot contain a cycle or reference themselves.'))
                seen.add(current.id)
                # Also serialize concurrent edits of different links in a chain.
                current._lock()
                current = current.dependency_request_id


class DeployTargetDependency(models.Model):
    _inherit = 'ab_deploy_target'

    def _dependency_blockers(self):
        """Return (target, safe reason) pairs; no access is granted to prerequisites."""
        blockers = []
        requests = self.request_id
        dependencies = requests.sudo().dependency_request_id
        if not dependencies:
            return blockers
        prerequisites = self.sudo().search(
            fields.Domain('request_id', 'in', dependencies.ids)
            & fields.Domain('server_id', 'in', self.server_id.ids))
        by_server = {(target.request_id.id, target.server_id.id): target for target in prerequisites}
        states = dict(self._fields['deployment_status']._description_selection(self.env))
        visible = {dependency.id: dependency.with_env(self.env).has_access('read')
                   for dependency in dependencies}
        for target in self:
            dependency = target.request_id.sudo().dependency_request_id
            if not dependency:
                continue
            prerequisite = by_server.get((dependency.id, target.server_id.id))
            status = prerequisite.deployment_status if prerequisite else False
            if status in ('succeeded', 'manually_resolved'):
                continue
            if not visible[dependency.id]:
                reason = _('Prerequisite not satisfied; details are restricted.')
            elif not prerequisite:
                reason = _('Server is not included in the prerequisite request.')
            else:
                reason = states[status]
            blockers.append((target, reason))
        return blockers

    def _validate_dependencies(self):
        blockers = self._dependency_blockers()
        if blockers:
            raise UserError(_('Cannot queue this selection. Prerequisite deployment has not succeeded or been manually resolved:\n%s',
                              '\n'.join('%s — %s' % (target.server_id.display_name, reason)
                                        for target, reason in blockers)))
