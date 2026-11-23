import ast

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


WORKFLOW_ADMIN_GROUP = 'ab_supplier_claim_cycle.supplier_claim_group_admin'
WORKFLOW_PARTICIPANT_GROUP = 'ab_supplier_claim_cycle.supplier_claim_group_participant'
SECRETARIAL_GROUP = 'ab_supplier_claim_cycle.supplier_claim_group_user'

STAGE_STATUSES = [
    ('waiting', 'Waiting'),
    ('pending', 'Pending'),
    ('deferred', 'Deferred'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
]


class SupplierClaimWorkflow(models.Model):
    _name = 'ab_supplier_claim_workflow'
    _description = 'Supplier Claim Workflow'
    _order = 'priority, name, version desc, id'

    name = fields.Char(required=True, translate=True)
    version = fields.Integer(default=1, required=True, readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'), ('published', 'Published'), ('archived', 'Archived'),
    ], default='draft', required=True, readonly=True, index=True)
    claim_domain = fields.Char(default='[]', required=True)
    priority = fields.Integer(default=10, required=True)
    workflow_stage_ids = fields.One2many(
        'ab_supplier_claim_workflow_stage', 'workflow_id', string='Stages', copy=True)
    active = fields.Boolean(default=True)
    can_reset_to_draft = fields.Boolean(compute='_compute_can_reset_to_draft')

    @api.depends('state')
    def _compute_can_reset_to_draft(self):
        used = self.env['ab_supplier_claim_stage_state'].sudo().search([
            ('stage_id.workflow_id', 'in', self.ids),
        ]).mapped('stage_id.workflow_id')
        for workflow in self:
            workflow.can_reset_to_draft = workflow.state == 'published' and workflow not in used

    def action_reset_to_draft(self):
        self._require_admin()
        self.lock_for_update()
        self.invalidate_recordset()
        if any(workflow.state != 'published' for workflow in self):
            raise UserError(_('Only unused published workflows can return to Draft.'))
        if self.env['ab_supplier_claim_stage_state'].sudo().search_count([
                ('stage_id.workflow_id', 'in', self.ids)], limit=1):
            raise UserError(_(
                'This workflow cannot return to Draft because it has already been used by a '
                'submitted claim, even if that claim is now closed, archived, or reset to Draft. '
                'Use New Version to create an editable draft workflow.'))
        result = super().write({'state': 'draft'})
        self.env['ab_supplier_claim_cycle'].sudo().with_context(active_test=False).search([
            ('workflow_id', 'in', self.ids), ('state', '=', 'draft'),
        ])._workflow_write({'workflow_id': False})
        return result

    _name_version_unique = models.Constraint(
        'UNIQUE(name, version)',
        'A workflow name and version must be unique.',
    )

    @api.model
    def _parse_domain(self, value):
        try:
            domain = ast.literal_eval(value or '[]')
        except (ValueError, SyntaxError, TypeError) as exc:
            raise ValidationError(_('The claim domain must be a literal Odoo domain.')) from exc
        if not isinstance(domain, (list, tuple)):
            raise ValidationError(_('The claim domain must be a list or tuple.'))
        domain = list(domain)
        try:
            fields.Domain(domain).validate(self.env['ab_supplier_claim_cycle'])
        except Exception as exc:
            raise ValidationError(_('Invalid claim domain: %s', exc)) from exc
        return domain

    @api.constrains('claim_domain')
    def _check_claim_domain(self):
        for workflow in self:
            workflow._parse_domain(workflow.claim_domain)

    @api.constrains('version')
    def _check_version(self):
        if any(workflow.version < 1 for workflow in self):
            raise ValidationError(_('Workflow versions must be positive.'))

    def _matches_claim(self, claim):
        self.ensure_one()
        claim.ensure_one()
        if self.state != 'published' or not self.active or not claim.id:
            return False
        domain = fields.Domain('id', '=', claim.id) & fields.Domain(
            self._parse_domain(self.claim_domain))
        return bool(claim.search_count(domain, limit=1))

    def action_publish(self):
        self._require_admin()
        for workflow in self:
            if workflow.state != 'draft':
                raise UserError(_('Only draft workflows can be published.'))
            if not workflow.workflow_stage_ids:
                raise ValidationError(_('Add at least one workflow stage before publishing.'))
            workflow._parse_domain(workflow.claim_domain)
            workflow.workflow_stage_ids._validate_for_publication()
        return super(SupplierClaimWorkflow, self).write({'state': 'published'})

    def action_archive_workflow(self):
        self._require_admin()
        self.lock_for_update()
        self.invalidate_recordset()
        if any(workflow.state != 'published' for workflow in self):
            raise UserError(_('Only published workflows can be archived.'))
        return super(SupplierClaimWorkflow, self).write({'state': 'archived', 'active': False})

    def _copy_as_new_version(self):
        self.ensure_one()
        next_version = max(self.with_context(active_test=False).search([
            ('name', '=', self.name),
        ]).mapped('version'), default=0) + 1
        return self.copy({
            'version': next_version,
            'state': 'draft',
            'active': True,
        })

    def _workflow_form_action(self, workflow):
        workflow.ensure_one()
        view = self.env.ref('ab_supplier_claim_cycle.supplier_claim_workflow_form')
        return {
            'type': 'ir.actions.act_window',
            'name': _('Workflow Version'),
            'res_model': self._name,
            'res_id': workflow.id,
            'view_mode': 'form',
            'views': [(view.id, 'form')],
            'target': 'current',
        }

    def action_new_version(self):
        self.ensure_one()
        self._require_admin()
        if self.state not in ('published', 'archived'):
            raise UserError(_('Create a new version from a published or archived workflow.'))
        return self._workflow_form_action(self._copy_as_new_version())

    def _restore_archived_workflows(self):
        self._require_admin()
        self.lock_for_update()
        self.invalidate_recordset()
        if any(workflow.state != 'archived' for workflow in self):
            raise UserError(_('Only archived workflows can be unarchived.'))

        used_ids = self.env['ab_supplier_claim_stage_state'].sudo().search([
            ('stage_id.workflow_id', 'in', self.ids),
        ]).mapped('stage_id.workflow_id').ids
        used = self.filtered(lambda workflow: workflow.id in used_ids)
        unused = self - used
        if used:
            super(SupplierClaimWorkflow, used).write({
                'state': 'published',
                'active': True,
            })
        if unused:
            super(SupplierClaimWorkflow, unused).write({
                'state': 'draft',
                'active': True,
            })
            self.env['ab_supplier_claim_cycle'].sudo().with_context(active_test=False).search([
                ('workflow_id', 'in', unused.ids),
                ('state', '=', 'draft'),
            ])._workflow_write({'workflow_id': False})
        return self

    def action_unarchive(self):
        self._restore_archived_workflows()
        return True

    def action_unarchive_workflow(self):
        self.ensure_one()
        workflow = self._restore_archived_workflows()
        return self._workflow_form_action(workflow)

    def _require_admin(self):
        if not (self.env.su or self.env.user.has_group(WORKFLOW_ADMIN_GROUP)
                or self.env.user.has_group('base.group_system')):
            raise AccessError(_('Only Supplier Claim Administrators can configure workflows.'))

    @api.model_create_multi
    def create(self, vals_list):
        self._require_admin()
        return super().create(vals_list)

    def write(self, vals):
        self._require_admin()
        if self.filtered(lambda workflow: workflow.state == 'archived'):
            raise AccessError(_('Archived workflow versions are immutable.'))
        published = self.filtered(lambda workflow: workflow.state == 'published')
        if published and set(vals) != {'workflow_stage_ids'}:
            raise AccessError(_(
                'Published workflows only allow safe stage updates. '
                'Create a new version for structural changes.'))
        return super().write(vals)

    def unlink(self):
        self._require_admin()
        if any(workflow.state != 'draft' for workflow in self):
            raise AccessError(_('Published workflow versions cannot be deleted.'))
        return super().unlink()


class SupplierClaimWorkflowStage(models.Model):
    _name = 'ab_supplier_claim_workflow_stage'
    _description = 'Supplier Claim Workflow Stage'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    workflow_id = fields.Many2one(
        'ab_supplier_claim_workflow', required=True, ondelete='cascade', index=True)
    allowed_field_ids = fields.Many2many(
        'ir.model.fields', 'ab_supplier_claim_stage_allowed_field_rel',
        'stage_id', 'field_id', string='Allowed Fields',
        domain=lambda self: self.env['ab_supplier_claim_workflow_stage']._allowed_field_domain())
    approver_ids = fields.Many2many(
        'res.users', 'ab_supplier_claim_stage_approver_rel',
        'stage_id', 'user_id', string='Approvers',
        domain="[('share', '=', False), ('active', '=', True)]")
    sequence = fields.Integer(default=10, required=True, index=True)

    _workflow_stage_name_unique = models.Constraint(
        'UNIQUE(workflow_id, name)',
        'Stage names must be unique within a workflow.',
    )

    @api.constrains('sequence')
    def _check_sequence(self):
        if any(stage.sequence < 1 for stage in self):
            raise ValidationError(_('Stage sequence must be positive.'))

    @api.model
    def _forbidden_allowed_fields(self):
        return {
            'id', 'state', 'active', 'user_id', 'company_id', 'create_uid', 'create_date',
            'write_uid', 'write_date', 'workflow_id', 'available_workflow_ids',
            'stage_state_ids', 'current_sequence', 'current_stage_names',
            'editable_field_names', 'rejection_stage_state_id', 'history_ids', 'document_ids',
        }

    @api.model
    def _allowed_field_domain(self):
        return [
            ('model', '=', 'ab_supplier_claim_cycle'),
            ('store', '=', True),
            ('compute', '=', False),
            ('related', '=', False),
            ('name', 'not in', sorted(self._forbidden_allowed_fields())),
        ]

    def _validate_for_publication(self):
        participant_group = self.env.ref(WORKFLOW_PARTICIPANT_GROUP)
        forbidden = self._forbidden_allowed_fields()
        for stage in self:
            if not stage.approver_ids:
                raise ValidationError(_('Stage "%s" requires at least one approver.', stage.name))
            invalid_users = stage.approver_ids.filtered(
                lambda user: not user.active or user.share or participant_group not in user.all_group_ids)
            if invalid_users:
                raise ValidationError(_(
                    'Every approver must be an active internal Supplier Claim Participant: %s',
                    ', '.join(invalid_users.mapped('display_name')),
                ))
            invalid_fields = stage.allowed_field_ids.filtered(
                lambda field: field.model != 'ab_supplier_claim_cycle'
                or not field.store or bool(field.compute) or bool(field.related)
                or field.name in forbidden)
            if invalid_fields:
                raise ValidationError(_(
                    'These fields cannot be controlled by a workflow stage: %s',
                    ', '.join(invalid_fields.mapped('field_description')),
                ))

    def _check_mutable(self):
        if any(stage.workflow_id.state != 'draft' for stage in self):
            raise AccessError(_('Stages of published workflow versions are immutable.'))

    @api.model_create_multi
    def create(self, vals_list):
        self.env['ab_supplier_claim_workflow']._require_admin()
        workflow_ids = {vals.get('workflow_id') for vals in vals_list if vals.get('workflow_id')}
        if self.env['ab_supplier_claim_workflow'].browse(workflow_ids).filtered(
                lambda workflow: workflow.state != 'draft'):
            raise AccessError(_('Stages can only be added to draft workflows.'))
        return super().create(vals_list)

    def write(self, vals):
        self.env['ab_supplier_claim_workflow']._require_admin()
        if vals.get('workflow_id') and self.env['ab_supplier_claim_workflow'].browse(
                vals['workflow_id']).state != 'draft':
            raise AccessError(_('Stages can only be moved to draft workflows.'))
        archived = self.filtered(lambda stage: stage.workflow_id.state == 'archived')
        if archived:
            raise AccessError(_('Stages of archived workflow versions are immutable.'))

        published = self.filtered(lambda stage: stage.workflow_id.state == 'published')
        if not published:
            return super().write(vals)

        allowed_changes = {'name', 'approver_ids', 'allowed_field_ids'}
        forbidden_changes = set(vals) - allowed_changes
        if forbidden_changes:
            raise AccessError(_(
                'Published stages only allow changing the stage name '
                'or updating approvers or allowed fields. Create a new version for other changes.'))

        previous_links = {
            stage.id: {
                'approver_ids': set(stage.approver_ids.ids),
                'allowed_field_ids': set(stage.allowed_field_ids.ids),
            }
            for stage in published
        }
        with self.env.cr.savepoint():
            result = super().write(vals)
            published._validate_for_publication()
            rows_by_stage = self.env['ab_supplier_claim_stage_state'].sudo().search([
                ('stage_id', 'in', published.ids),
            ]).grouped('stage_id')
            for stage in published:
                members = previous_links[stage.id]['approver_ids'] | set(stage.approver_ids.ids)
                rows = rows_by_stage.get(stage, self.env['ab_supplier_claim_stage_state'])
                rows._internal_write({
                    'historical_approver_ids': [fields.Command.link(user_id) for user_id in members],
                })
        return result

    def unlink(self):
        self.env['ab_supplier_claim_workflow']._require_admin()
        self._check_mutable()
        return super().unlink()


class SupplierClaimStageState(models.Model):
    _name = 'ab_supplier_claim_stage_state'
    _description = 'Supplier Claim Stage State'
    _order = 'sequence, id'

    stage_id = fields.Many2one(
        'ab_supplier_claim_workflow_stage', required=True, ondelete='restrict', index=True)
    claim_id = fields.Many2one(
        'ab_supplier_claim_cycle', required=True, ondelete='restrict', index=True)
    sequence = fields.Integer(related='stage_id.sequence', store=True, index=True)
    name = fields.Char(related='stage_id.name')
    approver_ids = fields.Many2many(related='stage_id.approver_ids', readonly=True)
    historical_approver_ids = fields.Many2many(
        'res.users', 'ab_supplier_claim_stage_historical_user_rel',
        'stage_state_id', 'user_id', readonly=True, copy=False)
    allowed_field_ids = fields.Many2many(
        related='stage_id.allowed_field_ids', readonly=True,
        domain=lambda self: self.env['ab_supplier_claim_workflow_stage']._allowed_field_domain())
    status = fields.Selection(STAGE_STATUSES, required=True, default='waiting', index=True)
    user_id = fields.Many2one('res.users', readonly=True, ondelete='restrict')
    decision_at = fields.Datetime(readonly=True)
    reason = fields.Text(readonly=True)
    followup_date = fields.Date(readonly=True)
    can_decide = fields.Boolean(compute='_compute_action_permissions')
    can_admin_undo = fields.Boolean(compute='_compute_action_permissions')

    _claim_stage_unique = models.Constraint(
        'UNIQUE(claim_id, stage_id)',
        'A workflow stage can occur only once on a claim.',
    )

    @api.depends('status', 'claim_id.state', 'claim_id.current_sequence', 'approver_ids')
    @api.depends_context('uid')
    def _compute_action_permissions(self):
        is_admin = self.env.su or self.env.user.has_group(WORKFLOW_ADMIN_GROUP)
        for stage_state in self:
            stage_state.can_decide = bool(
                stage_state.claim_id.active
                and stage_state.claim_id.state == 'in_progress'
                and stage_state.sequence == stage_state.claim_id.current_sequence
                and stage_state.status in ('pending', 'deferred')
                and stage_state.claim_id._is_stage_actor(stage_state)
            )
            stage_state.can_admin_undo = bool(
                is_admin and stage_state.claim_id.active
                and stage_state.claim_id.state != 'closed'
                and stage_state.status == 'approved'
            )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get('_supplier_claim_workflow_internal'):
            raise AccessError(_('Stage states are created only by workflow actions.'))
        return super(SupplierClaimStageState, self.sudo()).create(vals_list)

    def write(self, vals):
        if not self.env.context.get('_supplier_claim_workflow_internal'):
            raise AccessError(_('Stage states are changed only by workflow actions.'))
        return super(SupplierClaimStageState, self.sudo()).write(vals)

    @api.ondelete(at_uninstall=True)
    def _prevent_stage_state_deletion(self):
        if not self.env.context.get('_supplier_claim_workflow_internal'):
            raise AccessError(_('Stage states cannot be deleted.'))

    def _internal_write(self, vals):
        return self.with_context(_supplier_claim_workflow_internal=True).write(vals)

    def action_approve(self):
        return self.claim_id._action_stage_decision(self, 'approved')

    def action_open_reject(self):
        return self._open_decision_wizard('rejected')

    def action_open_defer(self):
        return self._open_decision_wizard('deferred')

    def action_open_admin_undo(self):
        return self._open_decision_wizard('undo')

    def _open_decision_wizard(self, decision):
        self.ensure_one()
        if decision == 'undo':
            if not self.can_admin_undo:
                raise AccessError(_('Only a Claim Administrator can remove this approval.'))
        elif not self.can_decide:
            raise AccessError(_('You cannot decide this stage.'))
        wizard = self.env['ab_supplier_claim_stage_decision'].create({
            'stage_state_id': self.id,
            'decision': decision,
        })
        view = self.env.ref(
            'ab_supplier_claim_cycle.view_supplier_claim_stage_decision_form')
        return {
            'type': 'ir.actions.act_window',
            'name': dict(wizard._fields['decision']._description_selection(self.env))[decision],
            'res_model': wizard._name,
            'res_id': wizard.id,
            'view_mode': 'form',
            'views': [(view.id, 'form')],
            'target': 'new',
        }


class SupplierClaimWorkflowEngine(models.Model):
    _inherit = 'ab_supplier_claim_cycle'

    workflow_id = fields.Many2one(
        'ab_supplier_claim_workflow', readonly=False, copy=False, tracking=True,
        domain="[('id', 'in', available_workflow_ids)]")
    available_workflow_ids = fields.Many2many(
        'ab_supplier_claim_workflow', compute='_compute_available_workflows')
    stage_state_ids = fields.One2many(
        'ab_supplier_claim_stage_state', 'claim_id', readonly=True, copy=False)
    current_sequence = fields.Integer(readonly=True, copy=False)
    current_stage_names = fields.Char(compute='_compute_current_stage_names')
    editable_field_names = fields.Json(compute='_compute_editable_field_names')
    rejection_stage_state_id = fields.Many2one(
        'ab_supplier_claim_stage_state', readonly=True, copy=False, ondelete='restrict')

    @api.model_create_multi
    def create(self, vals_list):
        clean_vals_list = []
        requested_workflow_ids = []
        for vals in vals_list:
            values = dict(vals)
            requested_workflow_ids.append(values.pop('workflow_id', False))
            clean_vals_list.append(values)
        claims = super().create(clean_vals_list)
        for claim, requested_workflow_id in zip(claims, requested_workflow_ids):
            claim.invalidate_recordset(['available_workflow_ids'])
            matching = claim.available_workflow_ids
            if requested_workflow_id:
                selected = matching.filtered(
                    lambda workflow: workflow.id == requested_workflow_id)
                if not selected:
                    raise ValidationError(_(
                        'The selected workflow does not match this draft claim.'))
            else:
                selected = matching if len(matching) == 1 else False
            if selected:
                claim._workflow_write({'workflow_id': selected.id})
        return claims

    @api.depends('supplier_id', 'num_of_invoice', 'area', 'claim_amount', 'type_of_invoice',
                 'payment_nature', 'tax_classification', 'section', 'claim_month', 'company_id', 'state')
    def _compute_available_workflows(self):
        workflows = self.env['ab_supplier_claim_workflow'].search([
            ('state', '=', 'published'), ('active', '=', True),
        ], order='priority, name, version desc, id')
        for claim in self:
            claim.available_workflow_ids = workflows.filtered(lambda workflow: workflow._matches_claim(claim))

    @api.onchange('supplier_id', 'num_of_invoice', 'area', 'claim_amount', 'type_of_invoice',
                  'payment_nature', 'tax_classification', 'section', 'claim_month')
    def _onchange_workflow_match(self):
        for claim in self.filtered(lambda record: record.state == 'draft' and record.id):
            matching = claim.available_workflow_ids
            if claim.workflow_id not in matching:
                claim.workflow_id = matching if len(matching) == 1 else False

    @api.depends('stage_state_ids.status', 'stage_state_ids.sequence',
                 'stage_state_ids.name', 'current_sequence')
    def _compute_current_stage_names(self):
        for claim in self:
            active = claim.stage_state_ids.filtered(
                lambda row: row.sequence == claim.current_sequence
                and row.status in ('pending', 'deferred', 'rejected'))
            claim.current_stage_names = ', '.join(active.mapped('name')) or False

    @api.model
    def _binary_companion_names(self, names):
        names = set(names)
        for name in tuple(names):
            if name == 'attachment':
                names.add('attachment_filename')
            elif name.endswith('_attachment'):
                companion = name[:-len('_attachment')] + '_filename'
                if companion in self._fields:
                    names.add(companion)
        return names

    def _editable_names_for_user(self):
        self.ensure_one()
        is_admin = self._is_admin()
        is_secretarial = is_admin or self.env.user.has_group(SECRETARIAL_GROUP)
        if self.state == 'draft' and is_secretarial:
            return set(self._entry_fields()) | {'workflow_id'}
        if self.state == 'returned' and is_secretarial and self.rejection_stage_state_id:
            return self._binary_companion_names(
                self.rejection_stage_state_id.sudo().allowed_field_ids.mapped('name'))
        if self.state != 'in_progress':
            return set()
        if not (is_admin or self.env.user.has_group(WORKFLOW_PARTICIPANT_GROUP)):
            return set()
        rows = self.stage_state_ids.filtered(
            lambda row: row.sequence == self.current_sequence
            and row.status in ('pending', 'deferred')
            and (is_admin or self.env.user in row.approver_ids))
        names = self._binary_companion_names(rows.sudo().mapped('allowed_field_ids.name'))
        if self._is_attachment_participant():
            for attachment, filename in self._attachment_field_pairs():
                if self[attachment]:
                    names -= {attachment, filename}
        return names

    @api.model
    def _attachment_field_pairs(self):
        return [('attachment', 'attachment_filename')] + [
            (kind + '_attachment', kind + '_filename')
            for kind in ('supplier_cheque', 'tax_review', 'payment_request', 'bank_cheque')]

    @api.depends('state', 'current_sequence', 'stage_state_ids.status',
                 'stage_state_ids.allowed_field_ids', 'stage_state_ids.approver_ids',
                 'rejection_stage_state_id', 'attachment', 'supplier_cheque_attachment',
                 'tax_review_attachment', 'payment_request_attachment', 'bank_cheque_attachment')
    @api.depends_context('uid')
    def _compute_editable_field_names(self):
        for claim in self:
            claim.editable_field_names = sorted(claim._editable_names_for_user())

    def _validate_selected_workflow(self, workflow):
        self.ensure_one()
        if not workflow or not workflow._matches_claim(self):
            raise ValidationError(_('Select a published workflow that matches this claim.'))

    def write(self, vals):
        if self.env.context.get('_supplier_claim_workflow_internal'):
            return self._workflow_write(vals)
        if self and all(claim.state == 'draft' and not claim.stage_state_ids for claim in self):
            workflow_value = vals.get('workflow_id') if 'workflow_id' in vals else None
            regular_vals = {name: value for name, value in vals.items() if name != 'workflow_id'}
            result = super().write(regular_vals) if regular_vals else True
            workflow = (self.env['ab_supplier_claim_workflow'].browse(workflow_value).exists()
                        if workflow_value is not None else False)
            for claim in self:
                claim.invalidate_recordset(['available_workflow_ids'])
                matching = claim.available_workflow_ids
                if workflow_value is not None:
                    if workflow:
                        claim._validate_selected_workflow(workflow)
                    selected = workflow
                elif claim.workflow_id in matching:
                    selected = claim.workflow_id
                else:
                    selected = matching if len(matching) == 1 else False
                if claim.workflow_id != selected:
                    claim._workflow_write({'workflow_id': selected.id if selected else False})
            return result
        protected = {
            'state', 'workflow_id', 'stage_state_ids', 'current_sequence',
            'rejection_stage_state_id', 'user_id', 'company_id', 'history_ids',
        }
        if set(vals) & protected:
            raise AccessError(_('Use workflow actions to change workflow-controlled fields.'))
        self.check_access('write')
        self.lock_for_update()
        self.invalidate_recordset()
        for claim in self:
            denied = set(vals) - claim._editable_names_for_user()
            if denied:
                raise AccessError(_(
                    'You may only edit fields assigned to your active stage: %s',
                    ', '.join(sorted(denied)),
                ))
        result = self._workflow_write(vals)
        for claim in self:
            for kind in ('attachment', 'supplier_cheque', 'tax_review',
                         'payment_request', 'bank_cheque'):
                attachment_field = 'attachment' if kind == 'attachment' else kind + '_attachment'
                filename_field = ('attachment_filename' if kind == 'attachment'
                                  else kind + '_filename')
                if attachment_field in vals and claim[attachment_field]:
                    self.env['ab_supplier_claim_document']._append({
                        'claim_id': claim.id,
                        'kind': kind,
                        'content': claim[attachment_field],
                        'filename': (vals.get(filename_field)
                                     if filename_field in vals else claim[filename_field]),
                        'revision': claim.document_revision,
                        'reason': 'Document uploaded',
                        'user_id': self.env.uid,
                        'occurred_at': fields.Datetime.now(),
                    })
            claim._log_generic('claim_updated', reason=_('Allowed stage fields were updated.'))
        return result

    def action_submit(self):
        self._require_role('user')
        self._prepare_action()
        StageState = self.env['ab_supplier_claim_stage_state'].with_context(
            _supplier_claim_workflow_internal=True)
        for claim in self:
            if claim.state == 'returned':
                claim.action_resubmit()
                continue
            if claim.state != 'draft':
                raise UserError(_('Only a draft claim can be submitted.'))
            claim._validate_submission_fields()
            if claim.stage_state_ids:
                if not claim.workflow_id:
                    raise UserError(_('The reset claim has no workflow snapshot to resume.'))
                stage_states = claim.stage_state_ids.sorted(
                    lambda row: (row.sequence, row.id))
                first_sequence = stage_states[0].sequence
                stage_states._internal_write({
                    'status': 'waiting', 'user_id': False, 'decision_at': False,
                    'reason': False, 'followup_date': False,
                })
                stage_states.filtered(
                    lambda row: row.sequence == first_sequence)._internal_write({
                        'status': 'pending',
                    })
                claim._workflow_write({
                    'state': 'in_progress',
                    'current_sequence': first_sequence,
                    'review_round': claim.review_round + 1,
                    'rejection_stage_state_id': False,
                })
                claim._log_generic('workflow_submitted', from_state='draft')
                continue
            matching = claim.available_workflow_ids
            workflow = claim.workflow_id or (matching if len(matching) == 1 else False)
            if not workflow:
                raise ValidationError(_('Select a published workflow that matches this claim.'))
            workflow.lock_for_update()
            workflow.invalidate_recordset()
            claim._validate_selected_workflow(workflow)
            stages = workflow.workflow_stage_ids.sorted(lambda stage: (stage.sequence, stage.id))
            if not stages:
                raise ValidationError(_('The selected workflow has no stages.'))
            first_sequence = stages[0].sequence
            StageState.create([{
                'claim_id': claim.id,
                'stage_id': stage.id,
                'historical_approver_ids': [fields.Command.set(stage.approver_ids.ids)],
                'status': 'pending' if stage.sequence == first_sequence else 'waiting',
            } for stage in stages])
            claim._workflow_write({
                'workflow_id': workflow.id,
                'state': 'in_progress',
                'current_sequence': first_sequence,
                'review_round': claim.review_round + 1,
                'rejection_stage_state_id': False,
            })
            claim._log_generic('workflow_submitted', from_state='draft')
        return True

    def action_reset_to_draft(self):
        self._require_role('admin')
        if not self:
            raise UserError(_('Select at least one claim to reset to Draft.'))
        self.check_access('write')
        self.lock_for_update()
        self.invalidate_recordset()
        self.check_access('write')
        if any(not claim.active for claim in self):
            raise UserError(_('Archived claims must be restored before resetting them to Draft.'))
        claims_to_reset = self.filtered(lambda record: record.state != 'draft')
        if not claims_to_reset:
            raise UserError(_('The selected claims are already in Draft.'))
        for claim in claims_to_reset:
            previous_state = claim.state
            claim.stage_state_ids._internal_write({
                'status': 'waiting', 'user_id': False, 'decision_at': False,
                'reason': False, 'followup_date': False,
            })
            claim._workflow_write({
                'state': 'draft',
                'current_sequence': 0,
                'rejection_stage_state_id': False,
            })
            claim._log_generic('reset_to_draft', from_state=previous_state)
        return True

    def action_resubmit(self):
        self._require_role('user')
        self._prepare_action()
        for claim in self:
            rejected = claim.rejection_stage_state_id
            if claim.state != 'returned' or not rejected or rejected.status != 'rejected':
                raise UserError(_('Only a returned claim can be resubmitted.'))
            rejected._internal_write({
                'status': 'pending', 'user_id': False, 'decision_at': False,
                'reason': False, 'followup_date': False,
            })
            claim._workflow_write({
                'state': 'in_progress',
                'current_sequence': rejected.sequence,
                'review_round': claim.review_round + 1,
                'rejection_stage_state_id': False,
            })
            claim._log_generic('workflow_resubmitted', from_state='returned', stage_state=rejected)
        return True

    def _is_stage_actor(self, stage_state):
        return self._is_admin() or (
            self.env.user.has_group(WORKFLOW_PARTICIPANT_GROUP)
            and self.env.user in stage_state.approver_ids
        )

    def _action_stage_decision(self, stage_state, decision, reason=None, followup_date=None):
        self.ensure_one()
        stage_state.ensure_one()
        if stage_state.claim_id != self:
            raise ValidationError(_('The stage does not belong to this claim.'))
        if decision not in ('approved', 'rejected', 'deferred'):
            raise ValidationError(_('Invalid stage decision.'))
        self._prepare_action()
        if not self._is_stage_actor(stage_state):
            raise AccessError(_('You are not an approver for this stage.'))
        if (self.state != 'in_progress' or stage_state.sequence != self.current_sequence
                or stage_state.status not in ('pending', 'deferred')):
            raise UserError(_('This stage is not currently actionable.'))
        clean_reason = (reason or '').strip()
        followup = fields.Date.to_date(followup_date) if followup_date else False
        if decision in ('rejected', 'deferred') and not clean_reason:
            raise ValidationError(_('A reason is required.'))
        if decision == 'deferred' and (
                not followup or followup < fields.Date.context_today(self)):
            raise ValidationError(_('Deferral requires a follow-up date today or later.'))
        old_state = self.state
        stage_state._internal_write({
            'status': decision,
            'user_id': self.env.uid,
            'decision_at': fields.Datetime.now(),
            'reason': clean_reason or False,
            'followup_date': followup,
        })
        if decision == 'approved':
            siblings = self.stage_state_ids.filtered(
                lambda row: row.sequence == self.current_sequence)
            if all(row.status == 'approved' for row in siblings):
                later = self.stage_state_ids.filtered(
                    lambda row: row.sequence > self.current_sequence and row.status == 'waiting')
                if later:
                    next_sequence = min(later.mapped('sequence'))
                    later.filtered(lambda row: row.sequence == next_sequence)._internal_write({
                        'status': 'pending',
                    })
                    self._workflow_write({'current_sequence': next_sequence})
                else:
                    self._workflow_write({'state': 'closed', 'current_sequence': 0})
        elif decision == 'rejected':
            self._workflow_write({
                'state': 'returned',
                'rejection_stage_state_id': stage_state.id,
            })
        self._log_generic('stage_decision', from_state=old_state, stage_state=stage_state,
                          decision=decision, reason=clean_reason, followup_date=followup)
        return True

    def action_admin_remove_approval(self, stage_state, reason):
        self.ensure_one()
        stage_state.ensure_one()
        if not self._is_admin():
            raise AccessError(_('Only a Claim Administrator can remove an approval.'))
        self._prepare_action()
        if self.state == 'closed':
            raise UserError(_('Closed claims are immutable.'))
        if stage_state.claim_id != self or stage_state.status != 'approved':
            raise UserError(_('Select an approved stage from this claim.'))
        clean_reason = (reason or '').strip()
        if not clean_reason:
            raise ValidationError(_('A reason is required to remove an approval.'))
        later = self.stage_state_ids.filtered(lambda row: row.sequence > stage_state.sequence)
        for row in later.filtered(lambda item: item.status != 'waiting'):
            self._log_generic('stage_invalidated', stage_state=row, reason=clean_reason)
        later._internal_write({
            'status': 'waiting', 'user_id': False, 'decision_at': False,
            'reason': False, 'followup_date': False,
        })
        stage_state._internal_write({
            'status': 'pending', 'user_id': False, 'decision_at': False,
            'reason': False, 'followup_date': False,
        })
        self._workflow_write({
            'state': 'in_progress',
            'current_sequence': stage_state.sequence,
            'rejection_stage_state_id': False,
        })
        self._log_generic('approval_removed', stage_state=stage_state, reason=clean_reason)
        return True

    def _log_generic(self, event, from_state=None, stage_state=None, decision=False,
                     reason=False, followup_date=False):
        self.ensure_one()
        values = {
            'claim_id': self.id,
            'event': event,
            'from_state': from_state or self.state,
            'to_state': self.state,
            'decision': decision or False,
            'reason': reason or False,
            'followup_date': followup_date or False,
            'review_round': self.review_round,
            'user_id': self.env.uid,
            'occurred_at': fields.Datetime.now(),
            'document_revision': self.document_revision,
            'tax_classification': self.tax_classification,
            'section': self.section,
        }
        if stage_state:
            values.update(
                stage_state_id=stage_state.id,
                stage_name=stage_state.name,
                stage_sequence=stage_state.sequence,
            )
        self.env['ab_supplier_claim_cycle.history']._append(values)

