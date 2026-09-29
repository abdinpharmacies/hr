import base64
import json
import resource
import time
from io import BytesIO
from unittest.mock import patch

from PIL import Image


def run_benchmark(env, label="after", size=250):
    env['ir.config_parameter'].sudo().set_param('ir_attachment.location', 'db')
    group = env['ab_product_group'].create({'name': 'Body Care L3'})
    tag = env['ab_product_tag'].create({'name': 'Sync Benchmark'})
    cards = env['ab_product_card'].create([
        {'name': 'Sync Benchmark %s' % i, 'description': 'Benchmark description', 'groups_ids': [(6, 0, group.ids)]}
        for i in range(size)
    ])
    products = env['ab_product'].create([
        {'product_card_id': card.id, 'name': 'Sync Benchmark %s' % i,
         'code': 'SYNC-BENCH-%s' % i, 'default_price': 25.0, 'default_cost': 10.0,
         'tag_ids': [(6, 0, tag.ids)], 'website_sale_available': True}
        for i, card in enumerate(cards)
    ])
    env.flush_all()
    rows = []
    Template = type(env['product.template'])
    original_write = Template.write

    def measure(scenario, creating=False):
        env.flush_all()
        env.invalidate_all()
        written = set()

        def record_write(records, values):
            written.update(records.ids)
            return original_write(records, values)

        queries = env.cr.sql_log_count
        start = time.perf_counter()
        cpu = time.process_time()
        with patch.object(Template, 'write', record_write):
            templates = products._sync_website_products()
            env.flush_all()
        elapsed = time.perf_counter() - start
        updated = 0 if creating else len(written & set(templates.ids))
        rows.append(dict(
            label=label, scenario=scenario, size=size, elapsed=round(elapsed, 3),
            products_sec=round(size / elapsed, 2), queries=env.cr.sql_log_count - queries,
            cpu_seconds=round(time.process_time() - cpu, 3),
            rss_peak_mb=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),
            created=size if creating else 0, updated=updated, noop=0 if creating else size - updated,
            exceptions=0,
        ))
        print(json.dumps(rows[-1]), flush=True)
        return templates

    templates = measure('initial_import_placeholder', creating=True)
    products.write({'default_price': 27.0})
    measure('changed_price')
    measure('unchanged_metadata')
    image = BytesIO()
    Image.new('RGB', (32, 32), (10, 150, 200)).save(image, format='PNG')
    templates.write({'image_1920': base64.b64encode(image.getvalue())})
    measure('existing_real_image')
    measure('image_unchanged_repeat')
    return rows
