import argparse
from datetime import datetime, timezone
import json
import re
import subprocess

import psycopg
from psycopg.rows import dict_row

from stages import database_options, read_private, write_result


def measure(intent_path):
    intent=read_private(intent_path)
    if intent.get('state')!='committed_to_odoo':
        raise ValueError('A committed authorized measurement intent is required')
    options='-c default_transaction_read_only=on -c statement_timeout=3000'
    with psycopg.connect(**database_options(),dbname='callcenter',options=options,row_factory=dict_row) as conn:
        operation=conn.execute('''SELECT o.id,o.token,o.attempt,o.state,o.create_date,o.write_date,o.provider_reference,o.history,
            a.provider,a.code AS account_code FROM ab_crm_messaging_operation o
            JOIN ab_crm_messaging_account a ON a.id=o.account_id WHERE o.id=%s AND o.token=%s''',
            (intent['operation_id'],intent['operation_token'])).fetchone()
    if operation is None:
        raise ValueError('Authorized operation mapping changed')
    config=read_private('/home/abdin_04/.config/crm-messaging/config.json')
    with psycopg.connect(config['database_url'],options=options,row_factory=dict_row) as conn:
        outgoing=conn.execute('''SELECT state,created_at,sends,outcome->>'status' AS outcome_status
            FROM outgoing_operation WHERE token=%s AND attempt=%s''',(operation['token'],operation['attempt'])).fetchone()
        callbacks=conn.execute('''SELECT state,created_at,payload->>'status' AS provider_status,attempts
            FROM incoming_event WHERE kind='status' AND payload->>'reference'=%s ORDER BY id''',
            (operation['provider_reference'],)).fetchall() if operation['provider_reference'] else []
    result={'mode':'authorized_'+operation['provider']+'_delivery_evidence','operation_id':operation['id'],
            'odoo_state':operation['state'],'operation_create_utc':operation['create_date'].replace(tzinfo=timezone.utc).isoformat(),
            'operation_write_utc':operation['write_date'].replace(tzinfo=timezone.utc).isoformat(),
            'queue_outgoing':outgoing,'callbacks':callbacks,'history':[
                {k:row[k] for k in ('status','error','at') if k in row} for row in operation['history'] or []],
            'observed_utc':datetime.now(timezone.utc).isoformat()}
    if outgoing:
        result['commit_to_gateway_queue_ms']=round((outgoing['created_at']-datetime.fromisoformat(intent['commit_utc'])).total_seconds()*1000,3)
    command=['journalctl','--user','-u','crm-messaging-pilot-'+operation['provider']+'.service','--since',intent['action_started_utc'],
             '--no-pager','-o','json','-n','1000']
    completed=subprocess.run(command,capture_output=True,text=True,timeout=10)
    spans=[]
    for line in completed.stdout.splitlines():
        try:
            row=json.loads(line)
        except ValueError:
            continue
        match=re.search(r'operation=provider_dispatch elapsed_ms=([0-9.]+)',row.get('MESSAGE',''))
        if match:
            spans.append({'elapsed_ms':float(match[1]),'completed_utc':datetime.fromtimestamp(
                int(row['__REALTIME_TIMESTAMP'])/1000000,timezone.utc).isoformat()})
    result['provider_dispatch_spans_in_window']=spans
    result['journal_exit_code']=completed.returncode
    result['limits']='Provider spans are time-window correlated, not transaction-ID traced. Receipt history has one-second precision. Odoo create_date can reflect transaction start, not actual creation/commit; use the intent commit clock for queue wait. No browser visibility measurement.'
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--intent-file',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    try:
        result=measure(args.intent_file)
        write_result(args.output,result)
    except Exception as exc:
        print(json.dumps({'error_category':type(exc).__name__}))
        raise SystemExit(1) from None
    print(json.dumps({'output':args.output,'odoo_state':result['odoo_state']}))


if __name__=='__main__':
    main()
