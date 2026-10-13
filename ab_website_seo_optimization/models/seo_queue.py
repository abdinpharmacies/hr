from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError
from odoo.addons.integration_queue_job.exception import RetryableJobError


_QUEUE_INTERNAL = object()


class SeoQueue(models.Model):
    _inherit = 'ab.product.seo.bulk.optimization'

    queue_checkpoint = fields.Integer(string='Queue Checkpoint', readonly=True, copy=False)
    queue_uuid = fields.Char(string='Queue Job UUID', readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        if any({'queue_checkpoint', 'queue_uuid'}.intersection(vals) for vals in vals_list):
            raise AccessError(_('Queue progress is maintained by the SEO worker.'))
        return super().create(vals_list)

    def write(self, vals):
        if {'queue_checkpoint', 'queue_uuid'}.intersection(vals) and self.env.context.get('seo_queue_internal') is not _QUEUE_INTERNAL:
            raise AccessError(_('Queue progress is maintained by the SEO worker.'))
        return super().write(vals)

    def _check_queue_access(self):
        self._require_manager()
        self.check_access('write')
        if not self.env.su and (not self.env.user.active or any(job.company_id not in self.env.user.company_ids for job in self)):
            raise AccessError(_('You cannot run SEO jobs for this company.'))

    def _lock_queue_run(self):
        self.ensure_one()
        self._check_queue_access()
        if not self.try_lock_for_update():
            raise RetryableJobError(_('SEO processing is busy. Try again shortly.'), seconds=10)
        self.invalidate_recordset()

    def _advance_queue_checkpoint(self):
        self.ensure_one()
        self.with_context(seo_queue_internal=_QUEUE_INTERNAL).write({
            'queue_checkpoint': self.queue_checkpoint + 1,
            'queue_uuid': False,
        })

    def _enqueue_queue_checkpoint(self, eta=None):
        self._lock_queue_run()
        if not self.active or self.state not in ('queued', 'running'):
            return
        if self.queue_uuid:
            existing = self.env['queue.job'].sudo().search(fields.Domain('uuid', '=', self.queue_uuid), limit=1)
            if existing.state in ('pending', 'enqueued', 'started', 'wait_dependencies'):
                return
        queued = self.with_company(self.company_id).with_context(allowed_company_ids=self.company_id.ids).with_delay(
            channel='root.seo',
            identity_key=f'seo:{self.id}:{self.queue_checkpoint}',
            description=_('SEO generation: %s', self.name),
            eta=eta,
            max_retries=5,
        )._process_queue_checkpoint(self.queue_checkpoint)
        self.with_context(seo_queue_internal=_QUEUE_INTERNAL).write({'queue_uuid': queued.uuid})

    def _enqueue_bulk_optimization(self):
        self._lock_queue_run()
        result = super()._enqueue_bulk_optimization()
        self._enqueue_queue_checkpoint()
        return result

    def _next_queue_eta(self):
        self.ensure_one()
        if not self.enrichment_enabled or not self.discovery_done:
            return None
        work = self.env['ab_seo_work_item']
        domain = fields.Domain('job_id', '=', self.id) & fields.Domain('state', 'in', ('queued', 'waiting'))
        now = fields.Datetime.now()
        ready = domain & (fields.Domain('next_attempt_at', '=', False) | fields.Domain('next_attempt_at', '<=', now))
        if work.search_count(ready, limit=1):
            return None
        waiting = work.search(domain, order='next_attempt_at, id', limit=1)
        return waiting.next_attempt_at if waiting else now + timedelta(seconds=60)

    def _process_queue_checkpoint(self, checkpoint):
        self._lock_queue_run()
        if not self.active or self.state not in ('queued', 'running') or checkpoint != self.queue_checkpoint:
            return
        if self.env.context.get('job_uuid') and self.env.context['job_uuid'] != self.queue_uuid:
            return
        run = self.with_company(self.company_id).with_context(allowed_company_ids=self.company_id.ids)
        previous_count = run.processed_count
        run._run_bulk_optimization_chunk()
        run._advance_queue_checkpoint()
        if run.state in ('queued', 'running'):
            eta = run._next_queue_eta()
            if not run.enrichment_enabled and run.processed_count == previous_count:
                eta = fields.Datetime.now() + timedelta(seconds=60)
            run._enqueue_queue_checkpoint(eta=eta)

    def action_resume_job(self):
        for run in self:
            run._lock_queue_run()
        result = super().action_resume_job()
        for run in self:
            run._advance_queue_checkpoint()
            run._enqueue_queue_checkpoint()
        return result

    def action_retry_failures(self):
        for run in self:
            run._lock_queue_run()
        result = super().action_retry_failures()
        for run in self:
            run._advance_queue_checkpoint()
            run._enqueue_queue_checkpoint()
        return result

    def action_cancel_batch(self):
        for run in self:
            run._lock_queue_run()
        return super().action_cancel_batch()


class SeoQueueRecord(models.Model):
    _inherit = 'ab.product.seo'

    def _optimize_single_published_product(self):
        result = super()._optimize_single_published_product()
        if not self.env.context.get('legacy_internal_seo'):
            self.last_bulk_id._enqueue_queue_checkpoint()
        return result
