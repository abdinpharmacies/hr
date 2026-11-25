"""Integration checks executed in an isolated Odoo shell; HTTP is always mocked.

See REVIEW.md for invocation. Keep this suite outside the production addon.
"""
import base64
import copy
import io
import json
import time
import unittest
import zipfile
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch, Mock

import requests
from odoo import fields
from odoo.exceptions import UserError
from odoo.addons.ab_tax_eta_archive.models.eta_policy import (
    CAIRO, TICK, api_stamp, api_inclusive_end, day_bounds, retrieval_cutoff, split_interval)
from odoo.addons.ab_tax_eta_archive.models.eta_sync import eta_task_lock, EtaRequestDeferred


class EtaArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = env  # supplied by odoo-bin shell
        cls.sync = env['ab_tax_eta_archive_sync']
        cls.exports = env['ab_tax_eta_archive_export']
        cls.configs = env['ab_tax_eta_archive_config']
        cls.today = datetime.now(CAIRO).date()

    def setUp(self):
        self.savepoint = self.env.cr.savepoint()
        self.savepoint.__enter__()
        self.config = self.configs.create({'name': 'ETA isolated test',
            'start_date': self.today - timedelta(days=90), 'safety_delay_hours': 0})
        self.auth = patch.object(type(self.config), '_eta_auth_headers',
                                 return_value=('https://eta.invalid', {'Authorization': 'test'}))
        self.auth.start()

    def tearDown(self):
        self.auth.stop()
        # Every test fixture is rolled back. Nothing is deleted from an archive.
        self.savepoint.__exit__(RuntimeError, RuntimeError('test rollback'), None)

    def run_day(self, kind='invoice', age=3, direction='sent'):
        return self.sync.create({'config_id': self.config.id, 'report_date': self.today-timedelta(days=age),
                                 'kind': kind, 'direction': direction})

    def item(self, run, number, stamp=None):
        stamp = stamp or api_stamp(day_bounds(run.report_date)[0] + timedelta(hours=1))
        return {'uuid': str(number), 'dateTimeIssued': stamp, 'dateTimeReceived': stamp,
                'currency': 'EGP', 'total': 10, 'totalAmount': 10, 'receiptNumber': str(number)}

    def invoice_page(self, items, token='EndofResultSet'):
        return {'result': items, 'metadata': {'continuationToken': token}}

    def receipt_page(self, items, total):
        return {'receipts': items, 'metadata': {'totalCount': total}}

    def test_invoice_partial_failure_resume_and_idempotency(self):
        run = self.run_day()
        first = self.invoice_page([self.item(run, 1)], 'next')
        last = self.invoice_page([self.item(run, 2)])
        with patch.object(type(run), '_request', side_effect=[first, UserError('transient'), last]) as request:
            self.assertTrue(run._attempt())
            self.assertEqual(run.state, 'partial')
            checkpoint = copy.deepcopy(run.checkpoint)
            self.assertFalse(run._attempt())
            self.assertEqual(run.checkpoint, checkpoint)
            self.assertEqual(run.item_count, 1)
            self.assertIn('transient', run.last_error)
            self.assertTrue(run._attempt())
            self.assertEqual(request.call_args.kwargs['params']['continuationToken'], 'next')
        self.assertEqual(run.state, 'done')
        self.assertEqual(run.item_count, 2)
        self.assertTrue(run.completed_at)
        with patch.object(type(run), '_request', side_effect=[first, last]):
            run._attempt(); run._attempt()
        self.assertEqual(run.item_count, 2)

    def test_invoice_more_than_twenty_pages_no_restarts(self):
        run = self.run_day()
        pages = [self.invoice_page([self.item(run, n)], str(n+1)) for n in range(24)]
        pages.append(self.invoice_page([self.item(run, 24)]))
        with patch.object(type(run), '_request', side_effect=pages) as request:
            for _ in pages:
                run._attempt()
        self.assertEqual(request.call_count, 25)
        self.assertEqual(run.state, 'done')
        self.assertEqual(run.item_count, 25)

    def test_receipt_pages_resume_without_probe(self):
        run = self.run_day('receipt')
        with patch.object(type(run), '_request', side_effect=[
                self.receipt_page([self.item(run, 1), self.item(run, 2)], 3),
                UserError('unavailable'), self.receipt_page([self.item(run, 3)], 3)]) as request:
            run._attempt()
            self.assertEqual(run.state, 'partial')
            run._attempt(); run._attempt()
            self.assertEqual(request.call_args.kwargs['params']['PageNo'], 2)
        self.assertEqual(run.state, 'done')
        self.assertEqual(run.item_count, 3)

    def test_receipt_count_change_never_done(self):
        run = self.run_day('receipt')
        with patch.object(type(run), '_request', side_effect=[
                self.receipt_page([self.item(run, 1)], 2),
                self.receipt_page([self.item(run, 2)], 3)]):
            run._attempt(); run._attempt()
        self.assertEqual(run.state, 'partial')
        self.assertEqual(run.item_count, 1)
        self.assertTrue(run.error_message)
        self.assertEqual(run.checkpoint['windows'][0]['page'], 2)

    def test_duplicate_receipt_page_rolls_back(self):
        run = self.run_day('receipt')
        with patch.object(type(run), '_request', side_effect=[
                self.receipt_page([self.item(run, 1)], 2),
                self.receipt_page([self.item(run, 1)], 2)]):
            run._attempt(); run._attempt()
        self.assertNotEqual(run.state, 'done')
        self.assertEqual(run.item_count, 1)

    def test_split_window_boundaries_and_independent_progress(self):
        run = self.run_day('receipt')
        with patch.object(type(run), '_request', return_value=self.receipt_page([], 3000)):
            run._attempt()
        a, b = run.checkpoint['windows']
        self.assertEqual(datetime.fromisoformat(a['end'].replace('Z','+00:00')) + TICK,
                         datetime.fromisoformat(b['start'].replace('Z','+00:00')))
        with patch.object(type(run), '_request', return_value=self.receipt_page([], 0)):
            run._attempt()
        self.assertEqual(len(run.checkpoint['windows']), 1)
        with patch.object(type(run), '_request', side_effect=UserError('failed right window')):
            run._attempt()
        self.assertEqual(run.checkpoint['windows'][0]['start'], b['start'])
        self.assertEqual(len(run.segment_ids), 1)

    def test_current_day_no_manual_or_scheduled_request(self):
        run = self.run_day(age=0)
        with patch.object(type(run), '_request') as request:
            run.action_retry()
            self.assertFalse(request.called)
        with patch.object(type(self.sync), '_ensure_run_days', return_value=True) as ensure:
            self.sync._cron_sync('invoice')
            self.assertLess(ensure.call_args.args[1], self.today)

    def test_safety_cutoff_partial_then_resume(self):
        run = self.run_day(age=1)
        start, end = day_bounds(run.report_date)
        with patch.object(type(self.config), '_retrieval_cutoff', return_value=start+timedelta(hours=12)), \
             patch.object(type(run), '_request', return_value=self.invoice_page([])) as request:
            run._attempt()
            self.assertEqual(request.call_args.kwargs['params']['submissionDateTo'],
                             api_inclusive_end(start+timedelta(hours=12)-TICK))
        self.assertEqual(run.state, 'partial')
        with patch.object(type(self.config), '_retrieval_cutoff', return_value=end), \
             patch.object(type(run), '_request', return_value=self.invoice_page([])) as request:
            run._attempt()
            self.assertEqual(request.call_args.kwargs['params']['submissionDateFrom'],
                             api_stamp(start+timedelta(hours=12)))
        self.assertEqual(run.state, 'done')

    def test_cutoff_cairo_delay_dst_and_milliseconds(self):
        now = datetime(2026, 11, 25, 4, tzinfo=timezone.utc)
        self.assertEqual(retrieval_cutoff(12, now), now-timedelta(hours=12))
        self.assertEqual(retrieval_cutoff(0, now), day_bounds(date(2026,11,25))[0])
        self.assertLess(retrieval_cutoff(12, now), day_bounds(date(2026,11,25))[0])
        lengths = [(day_bounds(date(2026,4,day))[1]-day_bounds(date(2026,4,day))[0]).total_seconds()/3600
                   for day in range(23,26)]
        self.assertIn(23, lengths)
        start = datetime(2026,1,1,tzinfo=timezone.utc)
        (a,b),(c,d)=split_interval(start,start+timedelta(milliseconds=2))
        self.assertEqual(b+TICK,c)
        self.assertEqual(d,start+timedelta(milliseconds=2))

    def test_operation_lock_overlap_and_exception_recovery(self):
        run = self.run_day()
        with eta_task_lock(self.env, -run.id) as acquired:
            self.assertTrue(acquired)
            with patch.object(type(run), '_retrieve') as retrieve:
                self.assertFalse(run._attempt())
                self.assertFalse(retrieve.called)
        try:
            with eta_task_lock(self.env, -run.id):
                raise RuntimeError('worker exit')
        except RuntimeError:
            pass
        with eta_task_lock(self.env, -run.id) as acquired:
            self.assertTrue(acquired)

    def test_long_range_creates_daily_windows_beyond_29_days(self):
        self.config.start_date = self.today-timedelta(days=90)
        self.assertTrue(self.sync._ensure_run_days(self.config,self.today-timedelta(days=1),kind='receipt'))
        runs=self.sync.search([('config_id','=',self.config.id)])
        self.assertEqual(len(runs),180)
        historical=runs.sorted('report_date')[0]
        historical._attempt()
        self.assertEqual(historical.state,'partial')
        self.assertEqual(len(historical.package_ids),1)

    def test_package_not_done_until_import_complete(self):
        run=self.run_day('receipt', age=45)
        run._attempt()
        part=run.package_ids
        stamp=api_stamp(day_bounds(run.report_date)[0]+timedelta(hours=1))
        items=[]
        for n in range(201):
            receipt={'uuid':str(n),'dateTimeIssued':stamp,'seller':{},'documentType':{},'itemData':[]}
            items.append({'receipt':receipt,'dateTimeReceived':stamp})
        part.write({'payload_json':json.dumps(items),'full_details':True,'state':'ready'})
        run._attempt()
        self.assertEqual(part.import_offset,200)
        self.assertEqual(part.state,'importing')
        self.assertEqual(run.state,'partial')
        run._attempt()
        self.assertTrue(part.imported)
        self.assertNotEqual(run.state,'done')
        run._attempt()
        self.assertEqual(run.state,'done')
        self.assertEqual(run.item_count,201)

    def test_package_split_and_end_not_extended(self):
        from odoo.addons.ab_tax_eta_archive.models.eta_sync import EtaSearchLimit
        run=self.run_day('receipt',age=45); run._attempt()
        parent=run.package_ids
        with patch.object(type(run),'_request',side_effect=EtaSearchLimit()) as request:
            run._attempt()
        query=request.call_args.kwargs['json']['queryParameters']
        self.assertEqual(query['dateTo'],api_inclusive_end(parent.end_at.replace(tzinfo=timezone.utc)))
        children=run.package_ids.filtered(lambda p:p.state!='split').sorted('start_at')
        self.assertEqual(len(children),2)
        self.assertEqual(children[0].end_at+TICK,children[1].start_at)

    def test_package_204_defers_polling_and_reuses_session(self):
        run=self.run_day('receipt',age=45); run._attempt()
        run.package_ids.package_id='pending-package'
        response=requests.Response(); response.status_code=204; response.raw=io.BytesIO()
        with patch.object(type(run),'_request',return_value=response) as request:
            self.assertFalse(run._attempt())
            self.assertFalse(run._attempt())
            self.assertEqual(request.call_count,1)
        self.assertGreater(run.next_attempt_at,fields.Datetime.now())
        self.assertNotEqual(run.state,'done')

    def test_cutoff_checkpoint_wait_does_not_spin(self):
        run=self.run_day(age=1)
        start,end=day_bounds(run.report_date)
        with patch.object(type(self.config),'_retrieval_cutoff',return_value=start+timedelta(hours=12)), \
             patch.object(type(run),'_request',return_value=self.invoice_page([])) as request:
            self.assertTrue(run._attempt())
            self.assertFalse(run._attempt())
            self.assertEqual(request.call_count,1)

    def test_package_throttle_preserves_retry_after(self):
        run=self.run_day('receipt',age=45); run._attempt()
        with patch.object(type(run),'_request',side_effect=EtaRequestDeferred(delay=600)):
            self.assertFalse(run._attempt())
        self.assertGreaterEqual(run.next_attempt_at,fields.Datetime.now()+timedelta(seconds=590))
        self.assertNotEqual(run.state,'done')

    def test_legacy_receipt_checkpoint_is_resumed(self):
        run=self.run_day('receipt')
        start,end=day_bounds(run.report_date)
        resume=start+timedelta(hours=10)
        run.write({'next_receipt_window_at':resume.replace(tzinfo=None),
                   'receipt_issue_dates_json':json.dumps({'basis':'received','issue_dates':[]})})
        with patch.object(type(run),'_request',return_value=self.receipt_page([],0)) as request:
            run._attempt()
        self.assertEqual(request.call_args.kwargs['params']['DateTimeReceivedFrom'],api_stamp(resume))

    def test_old_issue_checkpoint_is_preserved_but_not_used_as_submission_checkpoint(self):
        run=self.run_day('receipt')
        start,end=day_bounds(run.report_date)
        legacy=json.dumps({'basis':'issued','issue_dates':[]})
        run.write({'next_receipt_window_at':(start+timedelta(hours=10)).replace(tzinfo=None),
                   'receipt_issue_dates_json':legacy})
        with patch.object(type(run),'_request',return_value=self.receipt_page([],0)) as request:
            run._attempt()
        self.assertEqual(request.call_args.kwargs['params']['DateTimeReceivedFrom'],api_stamp(start))
        self.assertEqual(run.receipt_issue_dates_json,legacy)

    def test_late_receipt_uses_submission_day_and_keeps_issue_day(self):
        run=self.run_day('receipt')
        item=self.item(run,1)
        issue_day=run.report_date-timedelta(days=45)
        item['dateTimeIssued']=api_stamp(day_bounds(issue_day)[0]+timedelta(hours=1))
        with patch.object(type(run),'_request',return_value=self.receipt_page([item],1)):
            run._attempt()
        self.assertEqual(run.state,'done')
        self.assertEqual(run.item_count,1)
        row=self.env['ab_tax_eta_archive_receipt'].search([('config_id','=',self.config.id)])
        self.assertEqual(row.report_date,issue_day)

    def test_submillisecond_document_at_split_boundary(self):
        run=self.run_day('receipt')
        start,end=day_bounds(run.report_date)
        first,second=split_interval(start,end-TICK)
        run.checkpoint={'windows':[{'start':api_stamp(first[0]),'end':api_stamp(first[1])},
                                    {'start':api_stamp(second[0]),'end':api_stamp(second[1])}]}
        stamp=(first[1]+timedelta(microseconds=500)).isoformat().replace('+00:00','Z')
        with patch.object(type(run),'_request',return_value=self.receipt_page([self.item(run,1,stamp)],1)):
            run._attempt()
        self.assertFalse(run.error_message)
        self.assertEqual(run.item_count,1)

    def test_search_lock_shared_between_connections(self):
        run=self.run_day('receipt')
        other_config=self.config.copy({'name':'Same credentials'})
        other=self.sync.create({'config_id':other_config.id,'kind':'receipt','direction':'sent',
                                'report_date':run.report_date})
        session=Mock()
        def send(*args,**kwargs):
            with self.assertRaises(EtaRequestDeferred):
                other._request('GET','https://eta.invalid/api/v1/receipts/search',request_session=Mock())
            response=requests.Response(); response.status_code=200
            response._content=b'{}'; response.url='https://eta.invalid/api/v1/receipts/search'
            return response
        session.request.side_effect=send
        with patch('odoo.addons.ab_tax_eta_archive.models.eta_sync.time.sleep'):
            run._request('GET','https://eta.invalid/api/v1/receipts/search',request_session=session)

    def test_receipt_page_size_fallback(self):
        from odoo.addons.ab_tax_eta_archive.models.eta_sync import EtaPageSizeError
        run=self.run_day('receipt')
        with patch.object(type(run),'_request',side_effect=[EtaPageSizeError(),self.receipt_page([],0)]) as request:
            run._attempt()
        self.assertEqual(request.call_args.kwargs['params']['PageSize'],50)
        self.assertEqual(run.state,'done')

    def test_runtime_arabic_translation(self):
        self.env['res.lang']._activate_lang('ar_001')
        self.env['ir.module.module'].search([('name','=','ab_tax_eta_archive')])._update_translations(
            filter_lang=['ar_001'],overwrite=True)
        action=self.env.ref('ab_tax_eta_archive.action_eta_sync')
        self.assertNotEqual(action.with_context(lang='ar_001').name,action.with_context(lang='en_US').name)
        descriptions=self.config.with_context(lang='ar_001').fields_get(['safety_delay_hours'])
        self.assertEqual(descriptions['safety_delay_hours']['string'],'مهلة الأمان بالساعات')

    def ready_day(self):
        day=self.today-timedelta(days=3)
        self.sync.create([{'config_id':self.config.id,'report_date':day,'kind':kind,
                          'direction':direction,'state':'done'}
                         for kind in ('invoice','receipt') for direction in ('sent','received')])
        return day

    def test_missing_invoice_files_rebuilt_independently_and_reused(self):
        day=self.ready_day()
        for kind in ('receipt','invoice'):
            for direction in ('sent','received'):
                run=self.sync.search([('config_id','=',self.config.id),('kind','=',kind),
                                      ('direction','=',direction)])
                model=self.env['ab_tax_eta_archive_'+kind]
                values=model._eta_values(self.item(run,kind+direction),direction,self.config)
                values['detail_json']=json.dumps({'taxes':{},'rates':{},'total':10,'currency':'EGP'})
                model.create(values)
        original=self.exports._prepare(self.config,day,'sent_receipt','receipt','sent')
        original_data=original.file_data
        self.exports._ensure_files(self.config,day)
        latest=self.exports._latest_day_files(self.config,day)
        self.assertEqual(len(latest),4)
        self.assertTrue(all(r.generation_state=='ready' for r in latest.values()))
        self.assertEqual(original.file_data,original_data)
        self.assertTrue(self.exports._generation_complete(self.config,day))
        with patch.object(type(self.exports),'_prepare') as prepare:
            self.exports._ensure_files(self.config,day)
        self.assertFalse(prepare.called)

    def test_empty_waiting_and_failed_files_are_distinct_and_retryable(self):
        day=self.ready_day()
        self.exports._ensure_files(self.config,day)
        latest=self.exports._latest_day_files(self.config,day)
        self.assertTrue(all(r.generation_state=='empty' for r in latest.values()))
        run=self.sync.search([('config_id','=',self.config.id),('kind','=','invoice'),('direction','=','sent')])
        row=self.env['ab_tax_eta_archive_invoice'].create(dict(
            self.env['ab_tax_eta_archive_invoice']._eta_values(self.item(run,1),'sent',self.config),
            detail_json=json.dumps({'taxes':{},'rates':{},'total':10,'currency':'EGP'})))
        with patch.object(type(self.exports),'_prepare',side_effect=ValueError('bad file')):
            self.exports._ensure_files(self.config,day)
        self.assertEqual(latest['sent_invoice'].generation_state,'error')
        self.assertFalse(self.exports._generation_complete(self.config,day))
        self.exports._ensure_files(self.config,day)
        self.assertEqual(latest['sent_invoice'].generation_state,'ready')
        run.state='partial'
        self.exports._ensure_files(self.config,day)
        self.assertEqual(latest['sent_invoice'].generation_state,'waiting')
        self.assertTrue(latest['sent_invoice'].file_data)

    def test_transient_http_backoff_retry_after_and_single_refresh(self):
        run=self.run_day()
        def response(status,payload=None,headers=None):
            result=requests.Response(); result.status_code=status
            result.raw=io.BytesIO()
            result._content=json.dumps(payload or {}).encode(); result.url='https://eta.invalid/test'
            result.headers.update(headers or {})
            return result
        session=Mock()
        session.request.side_effect=[response(502),response(503),response(200,{'ok':True})]
        with patch('odoo.addons.ab_tax_eta_archive.models.eta_sync.time.sleep') as sleep:
            self.assertTrue(run._request('GET','https://eta.invalid/test',request_session=session)['ok'])
            self.assertEqual(sleep.call_count,2)
        session.request.side_effect=[response(401),response(401)]
        refresh=Mock(return_value={'Authorization':'refreshed'})
        with self.assertRaises(UserError):
            run._request('GET','https://eta.invalid/test',headers={},request_session=session,refresh_auth=refresh)
        self.assertEqual(refresh.call_count,1)
        session.request.side_effect=[response(429,headers={'Retry-After':'120'})]
        with self.assertRaises(EtaRequestDeferred):
            run._request('GET','https://eta.invalid/api/v1.0/documents/search',request_session=session)

    def test_sparse_receipt_request_count_benchmark(self):
        run=self.run_day('receipt')
        start=time.monotonic()
        with patch.object(type(run),'_request',return_value=self.receipt_page([],0)) as request:
            run._attempt()
        print('BENCHMARK empty receipt day: before=24 search probes; after=%s requests; local new=%.4fs'
              % (request.call_count,time.monotonic()-start))
        self.assertEqual(request.call_count,1)


result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(EtaArchiveTests))
env.cr.rollback()
if not result.wasSuccessful():
    raise RuntimeError('ETA validation failed')
