import base64
import json
import resource
import time
from io import BytesIO
from unittest.mock import patch
from PIL import Image
from odoo.addons.ab_website_sale_product.models import ab_product

env['ir.config_parameter'].sudo().set_param('ir_attachment.location', 'db')
group = env['ab_product_group'].create({'name': 'Body Care L3'})
tag = env['ab_product_tag'].create({'name': 'Batch Size Benchmark'})
cards = env['ab_product_card'].create([{'name': 'Batch Benchmark %s' % i, 'groups_ids': [(6, 0, group.ids)]} for i in range(5000)])
products = env['ab_product'].create([{'name': 'Batch Benchmark %s' % i, 'code': 'BATCH-BENCH-%s' % i,
    'product_card_id': card.id, 'default_price': 10.0, 'default_cost': 5.0, 'tag_ids': [(6, 0, tag.ids)]}
    for i, card in enumerate(cards)])
image = BytesIO()
Image.new('RGB', (32, 32), (0, 100, 200)).save(image, format='PNG')
payload = base64.b64encode(image.getvalue())
env['product.template'].create([{'name': p.name, 'ab_product_id': p.id, 'image_1920': payload} for p in products])
products._sync_website_products()
env.flush_all()
rows = []
for size in (250, 500, 1000, 2000, 5000):
    selected = products[:size]
    for scenario in ('unchanged', 'changed_price'):
        with env.cr.savepoint() as savepoint:
            if scenario == 'changed_price':
                selected.write({'default_price': 12.0})
            env.flush_all()
            env.invalidate_all()
            start = time.perf_counter()
            cpu = time.process_time()
            queries = env.cr.sql_log_count
            outcomes = {}
            with patch.object(ab_product, 'WEBSITE_SYNC_CHUNK_SIZE', size):
                selected._sync_website_products(outcomes=outcomes)
            env.flush_all()
            elapsed = time.perf_counter() - start
            row = dict(size=size, scenario=scenario, elapsed=round(elapsed, 3), products_sec=round(size/elapsed, 2),
                queries=env.cr.sql_log_count-queries, cpu_seconds=round(time.process_time()-cpu, 3),
                rss_peak_mb=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024, 1),
                created=sum(s == 'created' for s in outcomes.values()), updated=sum(s == 'updated' for s in outcomes.values()),
                noop=sum(s == 'unchanged' for s in outcomes.values()), exceptions=0)
            rows.append(row)
            print(json.dumps(row), flush=True)
            savepoint.close(rollback=True)
with open('/tmp/website_sync_batch_sizes.json', 'w') as output:
    json.dump(rows, output, indent=2)
