import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import signal
import sys
import time
from uuid import NAMESPACE_URL, uuid5

from result_io import write_result


class RollbackMeasurement(Exception):
    pass


class MeasurementBudgetExceeded(BaseException):
    pass


def run(phone,output):
    os.umask(0o077)
    digits=re.sub(r'\D','',phone)
    if digits.startswith('0'):
        digits='20'+digits[1:]
    if len(digits)!=12 or not digits.startswith('20'):
        raise ValueError('An explicitly authorized Egyptian test number is required')
    if Path(output).exists() or Path(str(output)+'.prepared').exists():
        raise ValueError('An existing test intent prevents uncertain replay')
    result={'mode':'normal_administrator_own_employee_chatter_tests',
            'started_utc':datetime.now(timezone.utc).isoformat(),'state':'prepared',
            'orm_samples_ms':{},'orm_budget_exceeded_ms':{},'sends':[]}
    write_result(str(output)+'.prepared',result)
    sys.path.insert(0,'/opt/odoo19/server')
    import odoo.init
    from odoo import api
    from odoo.modules import initialize_sys_path
    from odoo.modules.registry import Registry
    from odoo.service import server
    from odoo.tools import config
    config.parse_config(['-c','/opt/odoo19/conf/callcenter19.conf','-d','callcenter','--no-http',
        '--http-port=5069','--gevent-port=5072','--workers=0','--max-cron-threads=0',
        '--logfile=/tmp/callcenter-measure-chatter-shell.log'])
    initialize_sys_path()
    server.load_server_wide_modules()
    registry=Registry('callcenter')
    with registry.cursor() as cr:
        env=api.Environment(cr,2,{'allowed_company_ids':[1],'lang':'en_US'})
        chatter=env['ab_crm_chatter_api']
        profile=env['ab_employee_access'].search([('employee_id.user_id','=',env.uid)],limit=2)
        if len(profile)!=1 or not chatter._eligible(profile):
            result['state']='administrator_own_profile_not_eligible'
            cr.rollback()
        else:
            began=time.perf_counter()
            login=chatter.employee_login(profile.id,profile.pos_pin,'messaging-measure-20261125')
            result['normal_employee_login_ms']=round((time.perf_counter()-began)*1000,3)
            if not login.get('token'):
                raise ValueError('Normal own-profile employee login did not succeed')
            token=login['token']
            cr.commit()
            scoped=env(context=dict(env.context,ab_chatter_session_token=token,ab_chatter_inbox_only=True))
            conversations=scoped['ab_crm_conversation']
            test_message=scoped['ab_crm_message'].search([
                ('body','=','MEASURE-20261125'),('direction','=','in'),
                ('conversation_id.channel_id.provider','=','telegram')],order='id desc',limit=1)
            tg=test_message.conversation_id
            website=env['ab_crm_website_order'].search([
                ('account_id.code','=','website-production-reinstalled'),('chat_ready','=',True)],order='id desc')
            order=website.browse()
            for row in website:
                number=re.sub(r'\D','',row.phone or '')
                if number.startswith('0'):
                    number='20'+number[1:]
                if number==digits and not row.chat_closed:
                    order=row
                    break
            def measure(name,action):
                samples=[]
                def exceeded(signum,frame):
                    raise MeasurementBudgetExceeded()
                previous=signal.signal(signal.SIGALRM,exceeded)
                for _ in range(1):
                    began=time.perf_counter()
                    try:
                        with cr.savepoint():
                            signal.alarm(10)
                            action()
                            samples.append(round((time.perf_counter()-began)*1000,3))
                            raise RollbackMeasurement()
                    except RollbackMeasurement:
                        pass
                    except MeasurementBudgetExceeded:
                        result['orm_budget_exceeded_ms'][name]=round((time.perf_counter()-began)*1000,3)
                    finally:
                        signal.alarm(0)
                    scoped.invalidate_all(flush=False)
                signal.signal(signal.SIGALRM,previous)
                result['orm_samples_ms'][name]=samples
                print(json.dumps({'measured_stage':name,'samples_ms':samples,
                    'budget_exceeded_ms':result['orm_budget_exceeded_ms'].get(name)}),flush=True)
            try:
                measure('notifications_first_page',lambda:scoped['ab_crm_chatter_api'].notifications(token))
                measure('workspace_inbox',lambda:conversations.workspace_inbox())
                if tg:
                    measure('telegram_workspace_detail',lambda:conversations.browse(tg.id).workspace_detail(mark_read=False))
                if order:
                    measure('website_workspace_detail',lambda:conversations.browse(order.conversation_id.id).workspace_detail(mark_read=False))
                for provider,target in (('telegram',tg.id if tg else None),('website',order.conversation_id.id if order else None)):
                    if not target:
                        result['sends'].append({'provider':provider,'state':'matching_test_destination_missing'})
                        continue
                    body='TEST MEASURE-20261125: '+provider+' Sales Chatter queue timing check. No action is needed.'
                    record={'provider':provider,'conversation_id':target}
                    existing=scoped['ab_crm_message'].search([('body','=',body),('conversation_id','=',target)],limit=1)
                    if existing:
                        record.update(state='existing_test_requires_review',message_id=existing.id)
                        result['sends'].append(record)
                        continue
                    try:
                        with cr.savepoint():
                            began=time.perf_counter()
                            record['action_started_utc']=datetime.now(timezone.utc).isoformat()
                            if provider=='telegram':
                                message_id=conversations.browse(target).action_reply(body)
                            else:
                                message_id=conversations.browse(target).website_action_reply(body,
                                    website_order_id=order.id,submission_uuid=str(uuid5(NAMESPACE_URL,'measure-website-chatter-20261125:'+digits)))
                            operation=scoped['ab_crm_messaging_operation'].search([('message_id','=',message_id)],limit=2)
                            if len(operation)!=1:
                                raise ValueError('One test operation was expected')
                            record.update(message_id=message_id,operation_id=operation.id,operation_token=operation.token)
                        cr.commit()
                        record.update(state='committed_to_odoo',commit_utc=datetime.now(timezone.utc).isoformat(),
                            action_to_commit_ms=round((time.perf_counter()-began)*1000,3))
                    except Exception as exc:
                        cr.rollback()
                        record.update(state='rejected_rolled_back',error_category=type(exc).__name__)
                    result['sends'].append(record)
                result['state']='completed_normal_chatter_methods'
            finally:
                env.invalidate_all(flush=False)
                env['ab_crm_chatter_api'].logout(token)
                cr.commit()
                result['measurement_employee_session_closed']=True
    result['finished_utc']=datetime.now(timezone.utc).isoformat()
    result['limits']='Actual local ORM and authorization using administrator own employee profile. Read measurements rolled back to avoid auto-link/read side effects. No browser HTTP/render timing or regular staff-role load certification.'
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
    print(json.dumps({'output':args.output,'state':result['state'],
        'sends':[{k:v for k,v in row.items() if k!='operation_token'} for row in result['sends']]}))


if __name__=='__main__':
    main()
