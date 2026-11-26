import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
from uuid import NAMESPACE_URL, uuid5

import httpx
import psycopg
from psycopg.rows import dict_row

from stages import database_options, read_private, write_result


def run(phone,output):
    if Path(output).exists() or Path(str(output)+'.prepared').exists():
        raise ValueError('Existing intent prevents repeating an uncertain send')
    digits=re.sub(r'\D','',phone)
    if digits.startswith('0'):
        digits='20'+digits[1:]
    if len(digits)!=12 or not digits.startswith('20'):
        raise ValueError('An explicitly authorized Egyptian test number is required')
    config=read_private('/home/abdin_04/.config/crm-messaging/config-website-pilot.json')
    account=config['accounts']['website-production-reinstalled']
    if account['website_url']!='https://store.abdinpharmacies.com' or not account['sending_enabled']:
        raise ValueError('Production website account does not match the reviewed destination')
    with psycopg.connect(**database_options(),dbname='callcenter',
        options='-c default_transaction_read_only=on -c statement_timeout=5000',row_factory=dict_row) as conn:
        candidates=conn.execute('''SELECT o.id,o.order_uuid,o.phone FROM ab_crm_website_order o
            JOIN ab_crm_messaging_account a ON a.id=o.account_id
            WHERE a.code=%s AND a.provider_account=%s AND o.chat_ready IS TRUE AND o.chat_closed IS NOT TRUE
            ORDER BY o.id DESC''',('website-production-reinstalled',account['provider_account'])).fetchall()
    selected=None
    for row in candidates:
        other=re.sub(r'\D','',row['phone'] or '')
        if other.startswith('0'):
            other='20'+other[1:]
        if other==digits:
            selected=row
            break
    if selected is None:
        raise ValueError('No open website order mapped to the authorized test recipient')
    body='TEST MEASURE-20261125: website messaging latency check. No action is needed.'
    token=str(uuid5(NAMESPACE_URL,'callcenter-measure-20261125:'+digits+':website-reply'))
    result={'mode':'explicitly_authorized_single_website_test_reply','local_order_mapping_id':selected['id'],
        'idempotency_token':token,'started_utc':datetime.now(timezone.utc).isoformat(),
        'state':'prepared','limits':'Direct website exchange receive stage; does not measure Callcenter employee UI, queue scheduling or customer screen visibility.'}
    write_result(str(output)+'.prepared',result)
    began=time.perf_counter()
    try:
        with httpx.Client(timeout=15,follow_redirects=False,trust_env=False) as client:
            response=client.post(account['website_url']+'/storefront-callcenter/v4/receive',
                headers={'Authorization':'Bearer '+account['token'],'X-Odoo-Database':account['website_database']},
                json={'source':account['provider_account'],'destination_kind':'order',
                    'destination_uuid':selected['order_uuid'],'token':token,'body':body,'attachments':[]})
            result['elapsed_ms']=round((time.perf_counter()-began)*1000,3)
            result['http_status']=response.status_code
            result['state']='accepted' if response.status_code==200 and response.json()=={'reference':token} else 'rejected_or_unconfirmed'
    except Exception as exc:
        result['state']='unknown_requires_review'
        result['error_category']=type(exc).__name__
        result['elapsed_ms']=round((time.perf_counter()-began)*1000,3)
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
    print(json.dumps({k:v for k,v in result.items() if k!='idempotency_token'}))


if __name__=='__main__':
    main()
