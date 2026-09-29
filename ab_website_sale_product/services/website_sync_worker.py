import logging

from psycopg2 import OperationalError
from psycopg2.errors import DeadlockDetected, SerializationFailure

from odoo import SUPERUSER_ID, api, fields
from odoo.modules.registry import Registry

from ..models.website_product_sync_job import WEBSITE_SYNC_WORKER_LOCK

_logger = logging.getLogger(__name__)


def process_checkpoint(registry):
    job_id = None
    try:
        with registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            job = env["ab_website_product_sync_job"].search(
                fields.Domain("background_requested", "=", True)
                & fields.Domain("state", "in", ("draft", "running")), order="id", limit=1,
            )
            if not job:
                return False
            job_id = job.id
            processed = job._process_background_checkpoint()
            cr.commit()
            registry.signal_changes()
            return bool(processed)
    except (SerializationFailure, DeadlockDetected):
        _logger.warning("Website sync job %s checkpoint will be retried", job_id, exc_info=True)
        return False
    except OperationalError:
        raise
    except Exception as error:
        _logger.exception("Website sync job %s background processing stopped", job_id)
        if not job_id:
            raise
        with registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            job = env["ab_website_product_sync_job"].browse(job_id).exists()
            if job and job.background_requested and job.state in ("draft", "running"):
                job.write({"background_requested": False, "background_error": str(error)})
            cr.commit()
        return False


def run_worker(dbname, stop, poll_interval=2):
    registry = Registry(dbname)
    with registry.cursor() as lease:
        lease.execute("SELECT pg_try_advisory_lock(%s, %s)", WEBSITE_SYNC_WORKER_LOCK)
        if not lease.fetchone()[0]:
            _logger.info("A dedicated Website Product Sync worker already owns database %s", dbname)
            return
        lease.commit()
        try:
            _logger.info("Dedicated Website Product Sync worker ready for database %s", dbname)
            while not stop.is_set():
                lease.execute("SELECT 1")
                lease.commit()
                registry = registry.check_signaling()
                if not process_checkpoint(registry):
                    stop.wait(poll_interval)
        finally:
            lease.rollback()
            lease.execute("SELECT pg_advisory_unlock(%s, %s)", WEBSITE_SYNC_WORKER_LOCK)
            lease.commit()
            _logger.info("Dedicated Website Product Sync worker stopped for database %s", dbname)
