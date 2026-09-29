import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

from psycopg2.errors import SerializationFailure

from odoo import SUPERUSER_ID, api
from odoo.addons import ab_website_sale_product
from odoo.tools import config
from odoo.addons.ab_website_sale_product.services.website_sync_worker import process_checkpoint

assert env.cr.dbname.startswith('codex_website_sync_'), 'Requires an isolated test database'
registry = env.registry
Job = env['ab_website_product_sync_job']
Job.search([('state', '=', 'running')]).action_cancel()
env.cr.commit()
job = Job.create({'state': 'running', 'total_count': 751, 'batch_size_option': '15000'})
env['ab_website_product_sync_job_line'].create([{'job_id': job.id} for _index in range(751)])
job.write({'background_requested': True, 'background_user_id': env.uid,
           'background_company_id': env.company.id})
job_id = job.id
env.cr.commit()

with patch.object(type(Job), '_process_background_checkpoint', side_effect=SerializationFailure):
    assert not process_checkpoint(registry)


def fail_transaction(record):
    record.env.cr.execute('SELECT 1 / 0')


with patch.object(type(Job), '_process_background_checkpoint', fail_transaction):
    assert not process_checkpoint(registry)
env.invalidate_all()
assert job.processed_count == 0 and job.background_error and not job.background_requested
job.write({'background_requested': True, 'background_error': False})
env.cr.commit()
assert process_checkpoint(registry)
env.invalidate_all()
assert job.processed_count == 250
env.cr.commit()

module = Path(ab_website_sale_product.__file__).resolve().parent
command = [
    sys.executable, str(module / 'worker.py'), '--odoo-root=/opt/odoo19/server',
    '--config=' + config.rcfile, '--database=' + env.cr.dbname,
    '--addons-path=' + ','.join(config['addons_path']),
    '--data-dir=' + config['data_dir'], '--logfile=/tmp/website_sync_background_worker_test.log',
]


def wait_for(check, worker, timeout=40):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        assert worker.poll() is None, 'Worker exited unexpectedly'
        with registry.cursor() as cr:
            current = api.Environment(cr, SUPERUSER_ID, {})['ab_website_product_sync_job']
            if check(current):
                return
        time.sleep(0.1)
    raise AssertionError('Background worker timed out')


worker = subprocess.Popen(command, stdin=subprocess.DEVNULL)
try:
    wait_for(lambda current: current._background_worker_online(), worker)
    duplicate = subprocess.run(command, timeout=40, check=True)
    wait_for(lambda current: current.browse(job_id).state == 'done', worker)
    env.invalidate_all()
    assert job.processed_count == 751 and not job.background_requested
    assert set(job.line_ids.mapped('attempts')) == {1}
    env.cr.commit()

    next_job = Job.create({'state': 'running', 'total_count': 501, 'batch_size_option': '500'})
    env['ab_website_product_sync_job_line'].create([{'job_id': next_job.id} for _index in range(501)])
    started = time.monotonic()
    next_job.action_process_to_completion()
    elapsed = time.monotonic() - started
    assert elapsed < 1 and next_job.processed_count == 0
    next_job.action_process_to_completion()
    env.cr.commit()
    wait_for(lambda current: current.browse(next_job.id).state == 'done', worker)
    env.invalidate_all()
    assert next_job.processed_count == 501
    assert set(next_job.line_ids.mapped('attempts')) == {1}
    env.cr.commit()
    print('Checkpoint restart, independent process, duplicate worker exclusion, transaction recovery, and one-click completion passed; button %.4fs' % elapsed)
finally:
    worker.terminate()
    worker.wait(timeout=40)

assert not Job._background_worker_online()
env.cr.rollback()
