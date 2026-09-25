from odoo.addons.queue_job.controllers.main import RunJobController


class UploadRunJobController(RunJobController):
    @classmethod
    def _enqueue_dependent_jobs(cls, env, job):
        if job.model_name == "ab_odoo_sync_service" and job.method_name in {
            "job_send_branch_upload_batch", "job_send_historical_upload_batch",
        } and job.state != "done":
            # A postponed upload cannot release dependents. The runner's retry
            # path also leaves job.env pointing to its now-closed storage cursor.
            return
        return super()._enqueue_dependent_jobs(env, job)
