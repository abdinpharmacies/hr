import logging
from datetime import timedelta

from psycopg2.errors import DeadlockDetected, SerializationFailure

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.addons.integration_queue_job.exception import RetryableJobError

from .product_classification import check_manager
from ..services.classification import CATEGORY_ALIASES, DRUG_FORMS, classify_local, contains, normalize, taxonomy_key


_logger = logging.getLogger(__name__)
_FORCE_ACTIVE = ('queued', 'running')
_RESULT_FIELDS = ('status', 'method', 'node_id', 'proposed_node_id', 'confidence', 'classification_reason', 'ignored')
_ASSIGNMENT_FIELDS = ('mode', 'node_id', 'result_id', 'fingerprint')


def record_values(record, names):
    return {name: record[name].id if record._fields[name].type == 'many2one' else record[name] for name in names}


class ClassificationForceResult(models.Model):
    _inherit = 'ab_product_classification_result'

    force_suggested_node_id = fields.Many2one('ab_product_classification_taxonomy', compute='_compute_force_suggestion', string='Suggested Category')
    force_suggestion_reason = fields.Char(compute='_compute_force_suggestion', string='Suggestion Reason')
    force_suggestion_score = fields.Float(compute='_compute_force_suggestion', string='Suggestion Score', help='Evidence ranking from 0 to 100; this is not a measured probability.')
    force_current_category_ids = fields.Many2many(related='product_id.public_categ_ids', string='Current Website Categories')

    @api.depends('evidence', 'historical_evidence', 'product_id.public_categ_ids', 'proposed_node_id')
    def _compute_force_suggestion(self):
        nodes = self.env['ab_product_classification_taxonomy']._category_map()
        for row in self:
            node, reason, score = row._force_suggestion(nodes)
            row.force_suggested_node_id = node
            row.force_suggestion_reason = reason
            row.force_suggestion_score = score

    def _force_suggestion(self, nodes):
        self.ensure_one()
        empty = self.env['ab_product_classification_taxonomy']
        ready = {key: node.with_context(lang='en_US') for key, node in nodes.items() if node.ready}
        historical_paths = {tuple(item['mapped_path']) for item in self.historical_evidence or [] if item.get('mapped_path') and not item.get('promotional')}
        specific = {path for path in historical_paths if not any(len(other) > len(path) and other[:len(path)] == path for other in historical_paths)}
        if len(specific) == 1:
            node = ready.get(taxonomy_key(next(iter(specific))))
            if node:
                return node, self.env._('One category supported by historical evidence'), 75
        facts = self._facts()
        outcome = classify_local(facts)
        node = ready.get(taxonomy_key(outcome.get('path', ())))
        if node:
            return node, self.env._('Product data matches a classification rule'), outcome.get('confidence', 0) * 100
        categories = self.product_id.public_categ_ids.with_context(lang='en_US')
        matched = self.env['ab_product_classification_taxonomy']
        for node in ready.values():
            if node.category_id in categories.parents_and_self:
                matched |= node
        specific_nodes = matched.filtered(lambda node: not any(other.parent_id == node for other in matched))
        if len(specific_nodes) == 1:
            return specific_nodes, self.env._('Existing approved website category'), 65
        aliases = self.env['ab_product_classification_taxonomy']
        for category in categories:
            chain = category.parents_and_self
            names = {normalize(value) for value in chain.mapped('name')}
            for node in ready.values():
                root = node.parent_id or node
                root_names = {normalize(value) for value in (root.name, *CATEGORY_ALIASES.get(root.name, ()))}
                node_names = {normalize(value) for value in (node.name, *CATEGORY_ALIASES.get(node.name, ()))}
                if root_names & names and normalize(category.name) in node_names:
                    aliases |= node
        specific_aliases = aliases.filtered(lambda node: not any(other.parent_id == node for other in aliases))
        if len(specific_aliases) == 1:
            return specific_aliases, self.env._('Existing category name matches an approved category'), 55
        text = normalize(' '.join(str(facts.get(key) or '') for key in ('name', 'card_name', 'form')))
        if facts.get('is_medicine') and any(contains(text, term) for term in DRUG_FORMS + ('cap',)):
            node = ready.get('medicines')
            if node:
                return node, self.env._('Medicine flag and dosage form support the main category'), 30
        return empty, self.env._('Choose a category or use the automatic fallback'), 0

    def action_force_selected(self):
        check_manager(self.env)
        self.check_access('write')
        if len(self.run_id) != 1:
            raise UserError(self.env._('Select products from one classification run.'))
        return self.run_id._start_force('selected', self)

    def action_undo_force_selected(self):
        check_manager(self.env)
        self.check_access('write')
        if len(self.run_id) != 1:
            raise UserError(self.env._('Select products from one classification run.'))
        return self.run_id._start_force('undo', self)

    def _apply_force(self, node, reason, score, assignment):
        self.ensure_one()
        template = self.product_id or self.ab_product_id.website_product_tmpl_id
        previous = {
            'template_id': template.id,
            'result': record_values(self, _RESULT_FIELDS),
            'assignment': record_values(assignment, _ASSIGNMENT_FIELDS) if assignment else False,
            'category_ids': template.public_categ_ids.ids,
        }
        self._assign(node, 'forced', assignment)
        self._internal().write({
            'node_id': node.id, 'proposed_node_id': node.id, 'status': 'classified', 'method': 'forced',
            'confidence': score / 100, 'classification_reason': reason, 'ignored': False,
        })
        self.env['ab_product_classification_review']._internal().create({
            'result_id': self.id, 'decision': 'force', 'node_id': node.id,
            'reviewer_id': self.env.uid, 'previous_values': previous,
        })

    def _undo_force(self, assignment):
        self.ensure_one()
        review = self.env['ab_product_classification_review'].search([('result_id', '=', self.id)], order='id desc', limit=1)
        template = self.product_id or self.ab_product_id.website_product_tmpl_id
        if (
            not review or review.decision != 'force' or review.force_undone or not review.previous_values
            or not assignment or assignment.mode != 'forced' or assignment.result_id != self
            or assignment.node_id != review.node_id or self.method != 'forced'
            or (template and set(template.public_categ_ids.ids) != set(review.node_id.category_id.ids))
            or (review.previous_values and review.previous_values.get('template_id') != template.id)
        ):
            return False
        previous = review.previous_values
        categories = self.env['product.public.category'].browse(previous['category_ids']).exists()
        if len(categories) != len(previous['category_ids']):
            return False
        if template:
            template.sudo().write({'public_categ_ids': [fields.Command.set(categories.ids)]})
        assignment._internal().write(previous['assignment'] or {'mode': 'automatic', 'node_id': False, 'result_id': self.id, 'fingerprint': False})
        self._internal().write(previous['result'])
        review._internal().write({'force_undone': True})
        self.env['ab_product_classification_review']._internal().create({
            'result_id': self.id, 'decision': 'undo_force', 'reviewer_id': self.env.uid,
        })
        return True


class ClassificationForceReview(models.Model):
    _inherit = 'ab_product_classification_review'

    previous_values = fields.Json(readonly=True)
    force_undone = fields.Boolean(readonly=True)


class ClassificationForceRun(models.Model):
    _inherit = 'ab_product_classification_run'

    force_state = fields.Selection([('idle', 'Not Started'), ('queued', 'Queued'), ('running', 'Running'), ('done', 'Completed'), ('failed', 'Failed'), ('cancelled', 'Cancelled')], default='idle', readonly=True, string='Force Status')
    force_mode = fields.Selection([('selected', 'Selected Suggestions'), ('all', 'All Review Products'), ('undo', 'Undo Force Categorization')], readonly=True, string='Force Operation')
    force_result_ids = fields.Many2many('ab_product_classification_result', 'ab_classification_force_result_rel', 'run_id', 'result_id', readonly=True)
    force_fallback_node_id = fields.Many2one('ab_product_classification_taxonomy', readonly=True, string='Fallback Category')
    force_cursor = fields.Integer(readonly=True)
    force_total = fields.Integer(readonly=True, string='Products in Force Operation')
    force_processed = fields.Integer(readonly=True, string='Force Processed')
    force_applied = fields.Integer(readonly=True, string='Changes Applied')
    force_skipped = fields.Integer(readonly=True, string='Skipped Products')
    force_failed = fields.Integer(readonly=True, string='Force Failures')
    force_error = fields.Text(readonly=True, string='Force Error')
    force_queue_uuid = fields.Char(readonly=True)
    force_generation = fields.Integer(readonly=True)
    force_checkpoint = fields.Integer(readonly=True)
    force_requested_by = fields.Many2one('res.users', readonly=True)

    def action_force_preview(self):
        check_manager(self.env)
        self.ensure_one()
        self.check_access('read')
        return {
            'type': 'ir.actions.act_window', 'name': self.env._('Force Categorization Preview'),
            'res_model': 'ab_product_classification_result', 'view_mode': 'list,form',
            'views': [(self.env.ref('ab_website_sale_product.classification_force_preview_list').id, 'list'), (False, 'form')],
            'domain': [('run_id', '=', self.id), ('status', '=', 'needs_review'), ('ignored', '=', False)],
        }

    def action_force_all(self):
        check_manager(self.env)
        self.ensure_one()
        self.check_access('read')
        return {
            'type': 'ir.actions.act_window', 'name': self.env._('Automatically Assign All Review Products'),
            'res_model': 'ab_classification_force_wizard', 'view_mode': 'form', 'views': [(False, 'form')], 'target': 'new',
            'context': {'default_run_id': self.id},
        }

    def action_force_progress(self):
        check_manager(self.env)
        self.ensure_one()
        self.check_access('read')
        return {
            'type': 'ir.actions.act_window', 'name': self.env._('Force Categorization Progress'),
            'res_model': self._name, 'res_id': self.id, 'view_mode': 'form',
            'views': [(self.env.ref('ab_website_sale_product.classification_force_progress_form').id, 'form')],
        }

    def _start_force(self, mode, rows=None, fallback=None):
        check_manager(self.env)
        self.ensure_one()
        self.check_access('read')
        if mode not in ('selected', 'all', 'undo'):
            raise UserError(self.env._('Choose a valid force operation.'))
        if not self.env['ab_product']._lock_website_sync(wait=False):
            raise UserError(self.env._('A batch is being committed. Try again shortly.'))
        self._lock()
        Run = self.env[self._name]
        if Run.sudo().search_count(fields.Domain('state', 'in', ['queued', 'running', 'paused', 'stopping']) | fields.Domain('force_state', 'in', _FORCE_ACTIVE)):
            raise UserError(self.env._('Finish or stop the active classification operation first.'))
        nodes = self.env['ab_product_classification_taxonomy']._category_map()
        if not nodes or not all(node.ready for node in nodes.values()):
            raise UserError(self.env._('Prepare and resolve all approved taxonomy bindings before starting.'))
        if mode == 'all':
            if not fallback or not fallback.ready:
                raise UserError(self.env._('Choose a ready fallback category for products without a suggestion.'))
            rows = self.result_ids.filtered(lambda row: row.status == 'needs_review' and not row.ignored)
        elif not rows or rows.run_id != self:
            raise UserError(self.env._('Select products from this classification run.'))
        rows.check_access('write')
        if mode != 'undo':
            if any(row.status != 'needs_review' or row.ignored for row in rows):
                raise UserError(self.env._('Select only review products that have not been ignored.'))
            if mode == 'selected' and any(not (row.proposed_node_id or row._force_suggestion(nodes)[0]) for row in rows):
                raise UserError(self.env._('Choose a Review Category for selected products without a suggestion.'))
        if not rows:
            raise UserError(self.env._('There are no review products to assign.'))
        self._internal().write({
            'force_state': 'queued', 'force_mode': mode, 'force_result_ids': [fields.Command.set(rows.ids)],
            'force_fallback_node_id': fallback.id if fallback else False, 'force_cursor': 0, 'force_total': len(rows),
            'force_processed': 0, 'force_applied': 0, 'force_skipped': 0, 'force_failed': 0, 'force_error': False,
            'force_requested_by': self.env.uid, 'force_generation': self.force_generation + 1, 'force_checkpoint': 0,
        })
        self._enqueue_force()
        return self.action_force_progress()

    def _enqueue_force(self):
        self.ensure_one()
        job = self.with_user(self.force_requested_by).with_delay(
            channel='root.classification', identity_key=f'classification-force:{self.id}:{self.force_generation}:{self.force_checkpoint}',
            description=self.env._('Force Categorization %s', self.id), max_retries=10,
        )._force_checkpoint()
        self._internal().write({'force_queue_uuid': job.uuid})

    def _force_checkpoint(self):
        self.ensure_one()
        check_manager(self.env)
        self.check_access('read')
        if not self.env['ab_product']._lock_website_sync(wait=False) or not self.try_lock_for_update(allow_referencing=True):
            raise RetryableJobError(self.env._('A batch is being committed. Try again shortly.'), seconds=5, ignore_retry=True)
        self.invalidate_recordset()
        if self.force_state not in _FORCE_ACTIVE or (self.env.context.get('job_uuid') and self.env.context['job_uuid'] != self.force_queue_uuid):
            return
        run = self._internal()
        try:
            with self.env.cr.savepoint():
                if not self.force_requested_by.active or self.company_id not in self.force_requested_by.company_ids:
                    raise UserError(self.env._('The requester no longer has access to this company.'))
                rows = self.env['ab_product_classification_result'].search(
                    fields.Domain('id', 'in', self.force_result_ids.ids) & fields.Domain('id', '>', self.force_cursor), order='id', limit=100,
                )
                assignments = self.env['ab_product_classification_assignment'].search(fields.Domain('product_key', 'in', rows.mapped('product_key')))
                by_key = {assignment.product_key: assignment for assignment in assignments}
                nodes = self.env['ab_product_classification_taxonomy']._category_map()
                applied = skipped = failed = 0
                for row in rows:
                    try:
                        with self.env.cr.savepoint():
                            assignment = by_key.get(row.product_key, self.env['ab_product_classification_assignment'])
                            if self.force_mode == 'undo':
                                if row._undo_force(assignment):
                                    applied += 1
                                else:
                                    skipped += 1
                            elif row.status != 'needs_review' or row.ignored or (assignment and assignment.mode in ('manual', 'ignored', 'forced')):
                                skipped += 1
                            else:
                                node, reason, score = row._force_suggestion(nodes)
                                if row.proposed_node_id:
                                    node, reason, score = row.proposed_node_id, self.env._('Category chosen in the review preview'), 0
                                if not node and self.force_mode == 'all':
                                    node, reason, score = self.force_fallback_node_id, self.env._('Automatic fallback category chosen by the administrator'), 0
                                if not node or not node.ready:
                                    raise UserError(self.env._('The chosen category is not correctly bound to the approved taxonomy.'))
                                row._apply_force(node, reason, score, assignment)
                                applied += 1
                    except (SerializationFailure, DeadlockDetected):
                        raise
                    except Exception as error:
                        _logger.exception('Force categorization failed for result %s', row.id)
                        failed += 1
                        run.force_error = str(error)[:2000]
                self._refresh_counts()
                run.write({
                    'force_cursor': rows[-1].id if rows else self.force_cursor,
                    'force_processed': self.force_processed + len(rows), 'force_applied': self.force_applied + applied,
                    'force_skipped': self.force_skipped + skipped, 'force_failed': self.force_failed + failed,
                    'force_checkpoint': self.force_checkpoint + 1,
                    'force_state': 'running' if self.force_processed + len(rows) < self.force_total else 'done',
                })
                if self.force_state == 'running':
                    self._enqueue_force()
        except (SerializationFailure, DeadlockDetected):
            raise
        except Exception as error:
            _logger.exception('Force categorization operation failed for run %s', self.id)
            run.write({'force_state': 'failed', 'force_error': str(error)[:2000]})

    def action_cancel_force(self):
        check_manager(self.env)
        self._lock()
        self.filtered(lambda run: run.force_state in _FORCE_ACTIVE)._internal().write({'force_state': 'cancelled'})
        return True

    def get_status(self):
        result = super().get_status()
        result['force'] = {
            'state': self.force_state, 'total': self.force_total, 'processed': self.force_processed,
            'applied': self.force_applied, 'skipped': self.force_skipped, 'failed': self.force_failed, 'error': self.force_error or '',
        }
        return result

    @api.model
    def _recover_interrupted(self):
        result = super()._recover_interrupted()
        for run in self.search(fields.Domain('force_state', 'in', _FORCE_ACTIVE)):
            if not run.try_lock_for_update():
                continue
            job = self.env['queue.job'].sudo().search(fields.Domain('uuid', '=', run.force_queue_uuid), limit=1)
            if job.state == 'failed':
                run._internal().write({'force_state': 'failed', 'force_error': self.env._('The force queue job failed. Start a new force operation for the remaining products.')})
            elif job.state == 'started' and job.date_started and job.date_started < fields.Datetime.now() - timedelta(minutes=10):
                job.requeue()
            elif not job or job.state in ('done', 'cancelled'):
                run._internal().write({'force_checkpoint': run.force_checkpoint + 1})
                run._enqueue_force()
        return result


class ClassificationForceWizard(models.TransientModel):
    _name = 'ab_classification_force_wizard'
    _description = 'Automatic Force Categorization'

    run_id = fields.Many2one('ab_product_classification_run', required=True, readonly=True)
    review_count = fields.Integer(compute='_compute_review_count', string='Review Products')
    fallback_node_id = fields.Many2one('ab_product_classification_taxonomy', required=True, string='Fallback Category', help='Used only when no category suggestion is available. Select a main category or subcategory.')

    @api.depends('run_id')
    def _compute_review_count(self):
        for wizard in self:
            wizard.review_count = self.env['ab_product_classification_result'].search_count(fields.Domain('run_id', '=', wizard.run_id.id) & fields.Domain('status', '=', 'needs_review') & fields.Domain('ignored', '=', False))

    def action_start(self):
        check_manager(self.env)
        self.ensure_one()
        self.check_access('read')
        return self.run_id._start_force('all', fallback=self.fallback_node_id)
