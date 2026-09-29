import json
from unittest.mock import patch
from odoo import api, SUPERUSER_ID

if not env.cr.dbname.startswith('codex_website_sync_'):
    raise RuntimeError('Run only on an isolated codex_website_sync_ test database')
env['ab_website_product_sync_job'].search([('state', '=', 'running')]).write({'state': 'cancelled'})
env.flush_all()
products = env['ab_product'].create([
    {'name': 'Concurrency %s' % i, 'product_card_name': 'Concurrency %s' % i, 'code': 'SYNC-CONCURRENCY-%s' % i}
    for i in range(2)
])
job = env['ab_website_product_sync_job'].create({'state': 'running', 'total_count': 2})
job._add_product_lines(products)
job_id = job.id
env.cr.commit()
with env.registry.cursor() as cr1, env.registry.cursor() as cr2:
    first = api.Environment(cr1, SUPERUSER_ID, {'lang': 'en_US'})
    second = api.Environment(cr2, SUPERUSER_ID, {'lang': 'en_US'})
    j1 = first['ab_website_product_sync_job'].browse(job_id)
    j2 = second['ab_website_product_sync_job'].browse(job_id)
    assert j1.try_lock_for_update()
    assert not j2.try_lock_for_update()
    cr2.rollback()
    with patch.object(type(j1), '_get_batch_size', return_value=1):
        assert j1._process_next_batch()
    assert j1.processed_count == 1
    assert j2._process_next_batch()
    assert j2.processed_count == 0
    cr2.rollback()
    first['ir.cron']._commit_progress(1, remaining=1)
    second.invalidate_all()
    assert not j2._process_next_batch()
    assert j2.processed_count == 2
    second['ir.cron']._commit_progress(1, remaining=0)
with env.registry.cursor() as cr3:
    third = api.Environment(cr3, SUPERUSER_ID, {'lang': 'en_US'})
    completed = third['ab_website_product_sync_job'].browse(job_id)
    assert completed.state == 'done'
    assert not completed._process_next_batch()
    assert completed.processed_count == 2
    assert third['product.template'].search_count([('ab_product_id', 'in', products.ids)]) == 2
    print(json.dumps({'job_id': job_id, 'row_claim_exclusion': True, 'catalog_lock_exclusion': True,
        'committed_resume': True, 'duplicate_execution': 'no additional work', 'created': 2}), flush=True)
