"""Run before/after a targeted upgrade, ONLY in the dedicated review database."""
import base64
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from odoo.addons.ab_tax_eta_archive.models.eta_policy import CAIRO, day_bounds, api_stamp

assert env.cr.dbname == 'eta_review_20261125', 'Use the isolated review database only'
snapshot_path = Path('qa/ab_tax_eta_archive/upgrade_snapshot.json')
phase = os.environ.get('ETA_QA_PHASE', 'check')
config = env['ab_tax_eta_archive_config'].with_context(active_test=False).search([
    ('name', '=', 'Upgrade preservation fixture')])
if phase == 'prepare' and not config:
    day = datetime.now(CAIRO).date() - timedelta(days=10)
    config = env['ab_tax_eta_archive_config'].create({
        'name': 'Upgrade preservation fixture', 'active': False, 'start_date': day})
    stamp = api_stamp(day_bounds(day)[0] + timedelta(hours=1))
    for kind in ('invoice', 'receipt'):
        model = env['ab_tax_eta_archive_' + kind]
        values = model._eta_values({'uuid': 'upgrade-' + kind, 'dateTimeIssued': stamp,
                                    'dateTimeReceived': stamp}, 'sent', config)
        values['detail_json'] = '{"taxes":{"T1":12},"rates":{}}'
        model.create(values)
    env['ab_tax_eta_archive_sync'].create({
        'config_id': config.id, 'report_date': day, 'kind': 'invoice', 'direction': 'sent',
        'state': 'partial', 'item_count': 1, 'last_error': 'retained diagnostic',
        'checkpoint': {'windows': [{'start': stamp, 'end': api_stamp(day_bounds(day)[1]-timedelta(milliseconds=1)),
                                    'page': 2, 'token': 'qa-cursor'}]}})
    env['ab_tax_eta_archive_export'].create({
        'config_id': config.id, 'report_date': day, 'category': 'sent_invoice',
        'filename': 'preserve.xlsx', 'file_data': base64.b64encode(b'preservation-fixture'),
        'telegram_sent_at': datetime.now(timezone.utc).replace(tzinfo=None)})
    env.ref('ab_tax_eta_archive.cron_eta_sync').interval_number = 7

assert config
result = {}
for kind in ('invoice', 'receipt', 'sync', 'export'):
    model = env['ab_tax_eta_archive_' + kind]
    names = {'invoice': ['id','uuid','raw_json','detail_json'],
             'receipt': ['id','uuid','raw_json','detail_json'],
             'sync': ['id','state','item_count','checkpoint','last_error'],
             'export': ['id','filename','file_data','telegram_sent_at']}[kind]
    result[kind] = model.search([('config_id','=',config.id)], order='id').read(names)
result['interval'] = env.ref('ab_tax_eta_archive.cron_eta_sync').interval_number
serialized = json.dumps(result, default=str, sort_keys=True, ensure_ascii=True)
if phase == 'prepare':
    snapshot_path.write_text(serialized, encoding='utf-8')
    env.cr.commit()
    print('Prepared inactive archive fixtures and custom seven-minute cron interval')
else:
    assert snapshot_path.read_text(encoding='utf-8') == serialized
    assert result['interval'] == 7
    print('PASS targeted upgrade preserved documents, details, checkpoint, sent file, error, and custom schedule')
