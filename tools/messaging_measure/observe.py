import argparse
from datetime import datetime, timezone
import hashlib
import json
import time

import psycopg
from psycopg.rows import dict_row

from stages import database_options, read_private, write_result


def observe(marker,seconds):
    config=read_private('/home/abdin_04/.config/crm-messaging/config.json')
    options='-c default_transaction_read_only=on -c statement_timeout=3000'
    result={'mode':'authorized_marker_observation','marker':marker,
            'started_utc':datetime.now(timezone.utc).isoformat(),'events':[]}
    seen={}
    with psycopg.connect(config['database_url'],options=options,autocommit=True,row_factory=dict_row) as queue,psycopg.connect(
        **database_options(),dbname='callcenter',options=options,autocommit=True,row_factory=dict_row) as odoo:
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            rows=queue.execute("""SELECT id,account,state,created_at,payload->>'id' AS provider_id,
                payload->>'timestamp' AS provider_timestamp,payload->>'sender' AS sender,
                payload->'website_event'->>'event_uuid' AS website_id
                FROM incoming_event WHERE created_at>now()-interval '15 minutes'
                AND payload::text LIKE %s ORDER BY id""",('%'+marker+'%',)).fetchall()
            for row in rows:
                record=seen.setdefault(row['id'],{'queue_id':row['id'],'account':row['account'],
                    'queue_created_utc':row['created_at'].isoformat(),
                    'sender_digest':hashlib.sha256((row['sender'] or '').encode()).hexdigest()[:16],
                    'first_observed_utc':datetime.now(timezone.utc).isoformat()})
                record['queue_state']=row['state']
                if row['website_id']:
                    capture=odoo.execute('''SELECT e.create_date FROM ab_crm_website_chat_event e
                        JOIN ab_crm_messaging_account a ON a.id=e.account_id
                        WHERE a.code=%s AND e.event_uuid=%s''',(row['account'],row['website_id'])).fetchone()
                else:
                    capture=odoo.execute('''SELECT e.create_date,e.message_id FROM ab_crm_messaging_event e
                        JOIN ab_crm_messaging_account a ON a.id=e.account_id
                        WHERE a.code=%s AND e.event_key=%s''',(row['account'],row['provider_id'])).fetchone()
                if capture:
                    created=capture['create_date'].replace(tzinfo=timezone.utc)
                    record['odoo_create_utc']=created.isoformat()
                    record['queue_to_odoo_create_ms']=round((created-row['created_at']).total_seconds()*1000,3)
                    if capture.get('message_id'):
                        record['message_id']=capture['message_id']
                if row['provider_timestamp']:
                    origin=datetime.fromisoformat(row['provider_timestamp']).replace(tzinfo=timezone.utc)
                    record['provider_timestamp_to_queue_ms']=round((row['created_at']-origin).total_seconds()*1000,3)
            time.sleep(1)
    result['events']=list(seen.values())
    result['finished_utc']=datetime.now(timezone.utc).isoformat()
    result['limits']='Passive one-second observation; create_date is not commit time; sender identifiers are hashed; no message bodies or sends.'
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--marker',required=True)
    parser.add_argument('--seconds',type=int,default=180)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    if not 8<=len(args.marker)<=80 or not 5<=args.seconds<=300:
        parser.error('Use a marker of 8–80 characters and a bounded 5–300 second observation')
    try:
        result=observe(args.marker,args.seconds)
        write_result(args.output,result)
    except Exception as exc:
        print(json.dumps({'error_category':type(exc).__name__}))
        raise SystemExit(1) from None
    print(json.dumps({'output':args.output,'matched_events':len(result['events'])}))


if __name__=='__main__':
    main()
