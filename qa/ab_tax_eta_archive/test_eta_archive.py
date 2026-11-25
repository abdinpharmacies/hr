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
        run.package_ids.write({'remote_status':'2','status_checked_at':fields.Datetime.now()})
        response=requests.Response(); response.status_code=204; response.raw=io.BytesIO()
        with patch.object(type(run),'_request',return_value=response) as request:
            self.assertTrue(run._attempt())
            self.assertFalse(run._attempt())
            self.assertEqual(request.call_count,1)
        self.assertGreater(run.next_attempt_at,fields.Datetime.now())
        self.assertNotEqual(run.state,'done')

    def test_real_request_keeps_zip_response_and_imports_package(self):
        run=self.run_day('receipt',age=45); run._attempt()
        part=run.package_ids
        part.write({'package_id':'205882','remote_status':'2','status_checked_at':fields.Datetime.now()})
        stamp=api_stamp(day_bounds(run.report_date)[0]+timedelta(hours=1))
        items=[{'receipt':{'uuid':'zip-receipt','dateTimeIssued':stamp,'seller':{},
                            'documentType':{},'itemData':[]},'dateTimeReceived':stamp}]
        content=io.BytesIO()
        with zipfile.ZipFile(content,'w') as archive:
            archive.writestr('receipts.json',json.dumps(items))
        response=requests.Response(); response.status_code=200
        response._content=content.getvalue(); response._content_consumed=True
        response.url='https://eta.invalid/api/v1.0/receiptpackages/205882'
        session=Mock(); session.request.return_value=response
        run.with_context(eta_request_session=session)._attempt()
        self.assertEqual(session.request.call_args.kwargs['headers']['Accept'],'application/octet-stream')
        self.assertEqual(part.state,'ready')
        self.assertEqual(json.loads(part.payload_json),items)
        run._attempt(); run._attempt()
        self.assertEqual(run.state,'done')
        self.assertEqual(run.item_count,1)

    def test_real_request_returns_empty_204_without_json_parse(self):
        run=self.run_day('receipt')
        response=requests.Response(); response.status_code=204
        response.url='https://eta.invalid/package'; response.raw=io.BytesIO()
        session=Mock(); session.request.return_value=response
        result=run._request('GET',response.url,raw_response=True,request_session=session)
        self.assertIs(result,response)
        result.close()

    def test_flat_and_nested_http_diagnostics_preserve_codes_not_payload(self):
        from odoo.addons.ab_tax_eta_archive.models.eta_sync import EtaHttpError
        run=self.run_day('receipt')
        for payload in ({'code':'BadArgument','target':'rid','message':'secret receipt contents'},
                        {'error':{'code':'BadArgument','target':'rid','message':'secret receipt contents'}}):
            response=requests.Response(); response.status_code=400
            response._content=json.dumps(payload).encode(); response._content_consumed=True
            response.url='https://eta.invalid/package'; response.headers['correlationId']='qa-correlation'
            session=Mock(); session.request.return_value=response
            with self.assertRaises(EtaHttpError) as caught:
                run._request('GET',response.url,raw_response=True,request_session=session)
            self.assertIn('code=BadArgument',str(caught.exception))
            self.assertIn('target=rid',str(caught.exception))
            self.assertIn('qa-correlation',str(caught.exception))
            self.assertNotIn('secret receipt contents',str(caught.exception))

    def test_package_status_pagination_and_no_download_before_ready(self):
        run=self.run_day('receipt',age=45); run._attempt()
        part=run.package_ids; part.package_id='205882'
        with patch.object(type(run),'_request',side_effect=[
                {'result':[{'packageId':'other','status':2}],'metadata':{'totalPages':2}},
                {'result':[{'packageId':'205882','status':2}],'metadata':{'totalPages':2}}]) as request:
            run._attempt()
            self.assertEqual(part.status_page,1)
            run._attempt()
            self.assertEqual(request.call_count,2)
            self.assertTrue(all(c.args[1].endswith('/requests') for c in request.call_args_list))
        self.assertEqual(part.remote_status,'2')
        self.assertEqual(run.state,'partial')

    def test_package_failed_missing_never_mark_done_or_replace_id(self):
        for remote in (3,None):
            run=self.run_day('receipt',age=45+int(remote or 0)); run._attempt()
            part=run.package_ids; part.package_id='205882'
            rows=[] if remote is None else [{'packageId':'205882','status':remote}]
            with patch.object(type(run),'_request',return_value={
                    'result':rows,'metadata':{'totalPages':1}}) as request:
                run._attempt(); run._attempt()
            self.assertEqual(request.call_count,1)
            self.assertTrue(run.error_message)
            self.assertNotEqual(run.state,'done')
            self.assertEqual(part.package_id,'205882')

    def test_confirmed_expired_package_renews_with_history_and_bounded_attempts(self):
        run=self.run_day('receipt',age=45); run._attempt()
        part=run.package_ids; part.package_id='205882'
        with patch.object(type(run),'_request',return_value={
                'result':[{'packageId':'205882','status':4}], 'metadata':{'totalPages':1}}):
            run._attempt(); run._attempt()
        self.assertFalse(part.package_id)
        self.assertEqual(part.request_history[0]['package_id'],'205882')
        self.assertFalse(part.imported)
        self.assertNotEqual(run.state,'done')
        self.assertGreater(run.next_attempt_at,fields.Datetime.now())
        run.next_attempt_at=False
        part.write({'package_id':'expired-again','remote_status':'4',
                    'status_checked_at':fields.Datetime.now(), 'remote_error':'expired',
                    'request_history':[{'package_id':'old-one'},{'package_id':'old-two'}]})
        with patch.object(type(run),'_request') as request:
            run._attempt()
        self.assertFalse(request.called)
        self.assertIn('renewal limit',run.error_message)
        self.assertEqual(part.package_id,'expired-again')

    def test_package_400_rechecks_preparing_status_and_defers(self):
        from odoo.addons.ab_tax_eta_archive.models.eta_sync import EtaHttpError
        run=self.run_day('receipt',age=45); run._attempt()
        part=run.package_ids
        part.write({'package_id':'205882','remote_status':'2','status_checked_at':fields.Datetime.now()})
        with patch.object(type(run),'_request',side_effect=[EtaHttpError('HTTP 400 correlation qa',400),
                {'result':[{'packageId':'205882','status':1}],'metadata':{'totalPages':1}}]):
            run._attempt()
        self.assertEqual(part.remote_status,'1')
        self.assertGreater(run.next_attempt_at,fields.Datetime.now())
        self.assertNotEqual(run.state,'done')
        self.assertIn('correlation qa',run.last_error)

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
        file_labels=self.exports.with_context(lang='ar_001').fields_get(['file_verified_rows'])
        self.assertEqual(file_labels['file_verified_rows']['string'],'صفوف الملف')

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
                values['detail_json']=json.dumps({'taxes':{'T1':1.4},'rates':{'T1':14},
                                                   'total':10,'currency':'EGP'})
                model.create(values)
        original=self.exports._prepare(self.config,day,'sent_receipt','receipt','sent')
        original_data=original.file_data
        self.exports._ensure_files(self.config,day)
        latest=self.exports._latest_day_files(self.config,day)
        self.assertEqual(len(latest),4)
        self.assertTrue(all(r.generation_state=='ready' for r in latest.values()))
        from openpyxl import load_workbook
        for category,export in latest.items():
            workbook=load_workbook(io.BytesIO(base64.b64decode(export.file_data)),read_only=True)
            rows=list(workbook.active.values)
            self.assertEqual(len(rows),2)
            self.assertEqual(rows[1][11 if category.endswith('receipt') else 10],1.4)
            self.assertIn(category.replace('sent_','').replace('received_','')+
                          ('sent' if category.startswith('sent_') else 'received'),rows[1])
            workbook.close()
        self.assertEqual(original.file_data,original_data)
        self.assertTrue(self.exports._generation_complete(self.config,day))
        with patch.object(type(self.exports),'_prepare') as prepare:
            self.exports._ensure_files(self.config,day)
        self.assertFalse(prepare.called)

    def test_ready_files_are_queued_ahead_of_an_older_scan_cursor(self):
        day=self.ready_day()
        self.config.start_date=day-timedelta(days=15)
        old_cursor=day-timedelta(days=10)
        self.config.file_scan_date=old_cursor
        run=self.sync.search([('config_id','=',self.config.id),('kind','=','invoice'),('direction','=','sent')])
        self.env['ab_tax_eta_archive_invoice'].create(dict(
            self.env['ab_tax_eta_archive_invoice']._eta_values(self.item(run,'priority'),'sent',self.config),
            detail_json=json.dumps({'taxes':{},'rates':{},'total':10,'currency':'EGP'})))
        self.exports._queue_generation(self.config,day,'invoice','sent')
        export=self.exports._latest_day_files(self.config,day)['sent_invoice']
        self.assertTrue(export.generation_requested)
        self.assertEqual(self.config.file_scan_date,old_cursor)
        self.exports._prepare_files_batch()
        self.assertTrue(export.file_data)
        self.assertEqual(export.generation_state,'ready')
        self.assertFalse(export.generation_requested)

    def test_header_only_done_file_is_detected_and_rebuilt_without_new_data_event(self):
        from openpyxl import Workbook, load_workbook
        day=self.ready_day()
        self.config.start_date=day-timedelta(days=15)
        self.config.file_scan_date=day-timedelta(days=10)
        run=self.sync.search([('config_id','=',self.config.id),('kind','=','invoice'),('direction','=','sent')])
        self.env['ab_tax_eta_archive_invoice'].create([dict(
            self.env['ab_tax_eta_archive_invoice']._eta_values(self.item(run,'must-be-in-file-'+str(n)),'sent',self.config),
            detail_json=json.dumps({'taxes':{},'rates':{},'total':10,'currency':'EGP'})) for n in range(3)])
        export=self.exports._prepare(self.config,day,'sent_invoice','invoice','sent')
        workbook=Workbook(); workbook.active.append(['Header only'])
        workbook.active.cell(2,1).number_format='0.00'  # Styled blank row is not data.
        output=io.BytesIO(); workbook.save(output)
        export.write({'file_data':base64.b64encode(output.getvalue()),'generation_state':'ready',
                      'file_content_digest':False,'file_verified_rows':0})
        self.assertFalse(export._valid_file_content(3))
        self.exports._prepare_files_batch()
        workbook=load_workbook(io.BytesIO(base64.b64decode(export.file_data)),read_only=True)
        rows=list(workbook.active.values); workbook.close()
        self.assertEqual(len(rows),4)
        self.assertEqual({row[15] for row in rows[1:]},{'must-be-in-file-'+str(n) for n in range(3)})
        self.assertEqual(export.file_verified_rows,3)
        self.assertTrue(export._valid_file_content(3))

    def test_valid_sent_file_is_verified_without_rebuild_or_duplicate_revision(self):
        day=self.ready_day()
        run=self.sync.search([('config_id','=',self.config.id),('kind','=','invoice'),('direction','=','sent')])
        self.env['ab_tax_eta_archive_invoice'].create(dict(
            self.env['ab_tax_eta_archive_invoice']._eta_values(self.item(run,'keep-file'),'sent',self.config),
            detail_json=json.dumps({'taxes':{},'rates':{},'total':10,'currency':'EGP'})))
        export=self.exports._prepare(self.config,day,'sent_invoice','invoice','sent')
        original=export.file_data
        export.write({'telegram_sent_at':fields.Datetime.now(),'file_content_digest':False,'file_verified_rows':0})
        with patch.object(type(self.exports),'_prepare') as prepare:
            self.exports._ensure_files(self.config,day)
        self.assertFalse(prepare.called)
        self.assertEqual(export.file_data,original)
        self.assertEqual(export.revision,1)
        self.assertEqual(export.file_verified_rows,1)

    def test_file_generation_failure_is_queued_and_manual_retry_is_safe(self):
        day=self.ready_day()
        run=self.sync.search([('config_id','=',self.config.id),('kind','=','invoice'),('direction','=','sent')])
        self.env['ab_tax_eta_archive_invoice'].create(dict(
            self.env['ab_tax_eta_archive_invoice']._eta_values(self.item(run,'retry'),'sent',self.config),
            detail_json=json.dumps({'taxes':{},'rates':{},'total':10,'currency':'EGP'})))
        with patch.object(type(self.exports),'_prepare',side_effect=ValueError('test failure')):
            self.exports._ensure_files(self.config,day)
        export=self.exports._latest_day_files(self.config,day)['sent_invoice']
        self.assertTrue(export.generation_requested)
        self.assertGreater(export.generation_retry_at,fields.Datetime.now())
        with patch.object(type(self.exports),'_prepare') as prepare:
            self.exports.with_context(eta_generation_scheduled=True)._ensure_files(self.config,day)
        self.assertFalse(prepare.called)
        export.action_generate_files()
        self.assertEqual(export.generation_state,'ready')
        first=export.file_data
        export.action_generate_files()
        self.assertEqual(export.file_data,first)

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
