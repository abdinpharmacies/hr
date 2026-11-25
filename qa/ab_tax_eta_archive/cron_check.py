"""Exercise real Odoo cron transactions and committed page recovery; mocked HTTP."""
from datetime import datetime, timedelta
from unittest.mock import patch
from odoo.exceptions import UserError
from odoo.addons.ab_tax_eta_archive.models.eta_policy import CAIRO, api_stamp

assert env.cr.dbname == 'eta_review_20261125'
config = env['ab_tax_eta_archive_config'].create({
    'name': 'Real cron transaction fixture', 'start_date': datetime.now(CAIRO).date()-timedelta(days=2),
    'safety_delay_hours': 0})
env.cr.commit()
sync = env['ab_tax_eta_archive_sync']

def page(method, url, **options):
    params = options['params']
    if params['direction'] == 'Sent':
        return {'result': [], 'metadata': {'continuationToken': 'EndofResultSet'}}
    if params.get('continuationToken'):
        raise UserError('Forced page-two failure for transaction recovery check')
    stamp = api_stamp(datetime.fromisoformat(params['submissionDateFrom'].replace('Z', '+00:00'))
                      + timedelta(hours=1))
    return {'result': [{'uuid': 'cron-' + stamp, 'dateTimeIssued': stamp, 'dateTimeReceived': stamp}],
            'metadata': {'continuationToken': 'next'}}

try:
    with patch.object(type(config), '_eta_auth_headers', return_value=('https://eta.invalid', {})), \
         patch.object(type(sync), '_request', side_effect=page), \
         patch('requests.sessions.Session.request', side_effect=AssertionError('Live HTTP prohibited')):
        env.ref('ab_tax_eta_archive.cron_eta_sync').method_direct_trigger()
    # The callback uses its own transaction; refresh this shell's RR snapshot.
    env.cr.commit()
    env.invalidate_all()
    run = sync.search([('config_id', '=', config.id), ('direction', '=', 'received')], limit=1)
    assert run.state == 'partial' and run.item_count == 1
    assert run.checkpoint['windows'][0]['token'] == 'next'
    # A separate transaction sees the committed first page and its checkpoint.
    with env.registry.cursor() as cr:
        from odoo import api
        other = api.Environment(cr, env.uid, {})[sync._name].browse(run.id)
        assert other.state == 'partial' and other.item_count == 1
    with patch.object(type(config), '_eta_auth_headers', return_value=('https://eta.invalid', {})), \
         patch.object(type(sync), '_request', return_value={
             'result': [], 'metadata': {'continuationToken': 'EndofResultSet'}}):
        assert run._attempt()
    assert run.state == 'done' and run.item_count == 1
    print('PASS real Odoo cron: committed first page survives later failure and resumes to Done')
finally:
    config.active = False
    env.cr.commit()
