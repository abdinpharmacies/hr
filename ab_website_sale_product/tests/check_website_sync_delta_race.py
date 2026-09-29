from odoo import api, SUPERUSER_ID
from psycopg2.errors import SerializationFailure

if not env.cr.dbname.startswith('codex_website_sync_'):
    raise RuntimeError('Isolated test database required')
group = env['ab_product_group'].create({'name': 'Body Care L3'})
product = env['ab_product'].create({'name': 'Delta Race', 'product_card_name': 'Delta Race', 'code': 'SYNC-DELTA-RACE', 'groups_ids': [(6, 0, group.ids)]})
env.cr.commit()
with env.registry.cursor() as cr1, env.registry.cursor() as cr2:
    first = api.Environment(cr1, SUPERUSER_ID, {})
    second = api.Environment(cr2, SUPERUSER_ID, {})
    source = first['ab_product'].browse(product.id)
    assert source.website_sync_pending
    assert source.groups_ids.name == 'Body Care L3'
    other = second['ab_product'].browse(product.id)
    assert other.website_sync_pending
    second['ab_product_group'].browse(group.id).name = 'Pain Relief'
    second.flush_all()
    cr2.commit()
    try:
        source._sync_website_products()
        first.flush_all()
    except SerializationFailure:
        cr1.rollback()
        print('Concurrent related edit forces transaction retry; dirty marker preserved', flush=True)
    else:
        raise AssertionError('Related edit did not force retry; dirty marker may be lost')
