import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

from result_io import write_result


def run(phone,output):
    os.umask(0o077)
    digits=re.sub(r'\D','',phone)
    if digits.startswith('0'):
        digits='20'+digits[1:]
    if len(digits)!=12 or not digits.startswith('20'):
        raise ValueError('An explicitly authorized Egyptian test number is required')
    if Path(output).exists() or Path(str(output)+'.prepared').exists():
        raise ValueError('Existing intent prevents repeating an uncertain send')
    body='TEST MEASURE-20261125: Callcenter timing test reply. No action is needed.'
    result={'mode':'authorized_whatsapp_normal_odoo_dashboard_queue',
        'recipient_digest':hashlib.sha256(digits.encode()).hexdigest()[:16],
        'intent_utc':datetime.now(timezone.utc).isoformat(),'state':'prepared',
        'limits':'Normal administrator WhatsApp dashboard API, not employee Sales Chatter browser/PIN timing.'}
    write_result(str(output)+'.prepared',result)
    sys.path.insert(0,'/opt/odoo19/server')
    import odoo.init
    from odoo import api
    from odoo.modules import initialize_sys_path
    from odoo.modules.registry import Registry
    from odoo.service import server
    from odoo.tools import config
    config.parse_config(['-c','/opt/odoo19/conf/callcenter19.conf','-d','callcenter',
        '--no-http','--http-port=5069','--gevent-port=5072','--workers=0','--max-cron-threads=0',
        '--logfile=/tmp/callcenter-measure-odoo-shell.log'])
    initialize_sys_path()
    server.load_server_wide_modules()
    registry=Registry('callcenter')
    with registry.cursor() as cr:
        env=api.Environment(cr,2,{'allowed_company_ids':[1]})
        if env.user.login!='admin' or not env.user.has_group('base.group_system'):
            raise ValueError('Reviewed local administrator identity not found')
        existing=env['ab_crm_messaging_operation'].search([
            ('body','=',body),('destination','=',digits)],limit=1)
        if existing:
            result.update(state='existing_operation_requires_review',operation_id=existing.id)
        else:
            began=time.perf_counter()
            result['action_started_utc']=datetime.now(timezone.utc).isoformat()
            try:
                with cr.savepoint():
                    response=env['ab.whatsapp.service'].api_send_text(
                        to=digits,message=body,phone_number_id='965292690006920')
                    if not response.get('ok') or response.get('response')!={'queued':True}:
                        raise ValueError('Normal queue API did not confirm enqueue')
                    operation=env['ab_crm_messaging_operation'].search([
                        ('body','=',body),('destination','=',digits)],limit=2)
                    if len(operation)!=1:
                        raise ValueError('Expected exactly one new test operation')
                    result['operation_id']=operation.id
                    result['message_id']=operation.message_id.id
                    result['operation_token']=operation.token
                cr.commit()
                result.update(state='committed_to_odoo',commit_utc=datetime.now(timezone.utc).isoformat(),
                    action_to_commit_ms=round((time.perf_counter()-began)*1000,3))
            except Exception as exc:
                cr.rollback()
                result.update(state='rejected_rolled_back',error_category=type(exc).__name__,
                    action_elapsed_ms=round((time.perf_counter()-began)*1000,3))
    result['finished_utc']=datetime.now(timezone.utc).isoformat()
    write_result(output,result)
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--authorized-test-phone',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    try:
        result=run(args.authorized_test_phone,args.output)
    except Exception as exc:
        print(json.dumps({'error_category':type(exc).__name__}))
        raise SystemExit(1) from None
    print(json.dumps({k:v for k,v in result.items() if k!='operation_token'}))


if __name__=='__main__':
    main()
