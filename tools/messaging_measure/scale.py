import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import hmac
import json
import logging
import math
import os
from pathlib import Path
import sys
import threading
import time
from unittest.mock import Mock
from uuid import uuid4
from urllib.parse import urlencode

import httpx
import psycopg
from psycopg import sql
from fastapi.testclient import TestClient

from stages import database_options, distribution, write_result, ROOT
from app.config import Account, Settings
from app.main import create_app
from app.storage import Store
from app.worker import Worker


PAGE_SQL = """SELECT c.id FROM scale_conversation c
    WHERE c.company_id=1 AND c.branch_id=1 AND c.id>%s
    AND EXISTS(SELECT 1 FROM scale_message m WHERE m.conversation_id=c.id AND m.direction='in')
    ORDER BY c.id LIMIT 51"""


@contextmanager
def isolated_database():
    name='cc_measure_test_'+uuid4().hex[:12]
    options=database_options()
    with psycopg.connect(**options,dbname='postgres',autocommit=True) as admin:
        admin.execute(sql.SQL('CREATE DATABASE {} TEMPLATE template0').format(sql.Identifier(name)))
    dsn='postgresql:///'+name+'?'+urlencode(options)
    try:
        with psycopg.connect(dsn) as conn:
            conn.execute('CREATE TABLE measure_guard (identity text PRIMARY KEY)')
            conn.execute('INSERT INTO measure_guard VALUES (%s)',(name,))
        yield name,dsn
    finally:
        with psycopg.connect(dsn) as conn:
            marker=conn.execute('SELECT identity FROM measure_guard').fetchone()[0]
        if marker!=name or not name.startswith('cc_measure_test_'):
            raise RuntimeError('Refusing cleanup of unowned database')
        with psycopg.connect(**options,dbname='postgres',autocommit=True) as admin:
            admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))


def clocked(samples,name,action):
    began=time.perf_counter()
    result=action()
    samples[name].append((time.perf_counter()-began)*1000)
    return result


def queue_stages(dsn,cycles=60):
    samples=defaultdict(list)
    store=Store(dsn)
    store.migrate()
    account=Account(provider='whatsapp',provider_account='456',token='synthetic-provider-key',
                    odoo_key='synthetic-odoo-key',webhook_secret='synthetic-webhook-secret',
                    verify_token='synthetic-verify',enabled=True,sending_enabled=True,reception='webhook')
    config=Settings(database_url=dsn,odoo_url='https://synthetic.invalid',odoo_database='synthetic',
                    odoo_key='synthetic-odoo-key',accounts={'benchmark':account},sending_enabled=True)
    odoo=Mock()
    odoo.call.return_value=True
    worker=Worker(config,store,odoo,Mock(),accounts=['benchmark'])
    worker._send_operation=Mock(return_value={'status':'accepted','reference':'synthetic','error':'none'})
    with TestClient(create_app(config,store)) as client:
        for number in range(cycles):
            event={'object':'whatsapp_business_account','entry':[{'changes':[{'field':'messages','value':{
                'metadata':{'phone_number_id':'456'},'messages':[{'id':f'synthetic-{number}',
                'from':f'2010000{number:06d}','timestamp':str(int(time.time())),
                'type':'text','text':{'body':'Synthetic timing test'}}]}}]}]}
            raw=json.dumps(event,separators=(',',':')).encode()
            signature='sha256='+hmac.new(b'synthetic-webhook-secret',raw,hashlib.sha256).hexdigest()
            response=clocked(samples,'signed_whatsapp_webhook_to_pg_commit',lambda:client.post(
                '/webhooks/whatsapp/benchmark',content=raw,
                headers={'Content-Type':'application/json','X-Hub-Signature-256':signature}))
            if response.status_code!=200:
                raise RuntimeError('Synthetic webhook failed')
            clocked(samples,'worker_incoming_pg_claim_mock_odoo_finish',worker.ingest)
            payload={'token':str(uuid4()),'attempt':1,'lease':'synthetic-lease','destination':str(number),
                     'body':'Synthetic timing test','provider':'whatsapp','provider_account':'456'}
            odoo.call.return_value=payload
            clocked(samples,'outgoing_collect_pg_store_mock_odoo_receipt',lambda:worker.collect('benchmark'))
            odoo.call.return_value=True
            clocked(samples,'dispatch_pg_claim_mock_auth_mock_provider_outcome',worker.dispatch)
            clocked(samples,'report_pg_read_mock_odoo_mark_done',worker.report)
    with store.connect() as conn:
        unfinished=conn.execute("SELECT count(*) AS n FROM incoming_event WHERE state!='done'").fetchone()['n']
        unfinished+=conn.execute("SELECT count(*) AS n FROM outgoing_operation WHERE state!='done'").fetchone()['n']
    if unfinished:
        raise RuntimeError('Synthetic stage work unfinished')
    return {'cycles':cycles,'stages':{key:distribution(value) for key,value in samples.items()},
            'real_components':['current FastAPI app','HMAC verification','normalization','current Store and Worker code','PostgreSQL commits'],
            'mocked_components':['Odoo business methods','provider send','network between components'],
            'unfinished':unfinished}


def seed(conn,customers):
    conn.execute('CREATE TABLE scale_customer (id integer PRIMARY KEY,company_id integer,branch_id integer,name text,phone text)')
    conn.execute('CREATE TABLE scale_conversation (id integer PRIMARY KEY,company_id integer,branch_id integer,customer_id integer)')
    conn.execute('CREATE TABLE scale_message (id integer PRIMARY KEY,conversation_id integer,direction text,branch_share_token text)')
    conn.execute("INSERT INTO scale_customer SELECT i,1,1,'Synthetic customer '||i,lpad(i::text,13,'0') FROM generate_series(1,%s) AS i",(customers,))
    conn.execute('INSERT INTO scale_conversation SELECT id,company_id,branch_id,id FROM scale_customer')
    conn.execute("INSERT INTO scale_message SELECT id,id,'in',NULL FROM scale_customer")
    conn.execute('CREATE INDEX ON scale_customer (phone)')
    for table in ('scale_customer','scale_conversation'):
        for col in ('company_id','branch_id'):
            conn.execute(sql.SQL('CREATE INDEX ON {} ({})').format(sql.Identifier(table),sql.Identifier(col)))
    conn.execute('CREATE UNIQUE INDEX ON scale_message (conversation_id,branch_share_token)')
    for table in ('scale_customer','scale_conversation','scale_message'):
        conn.execute(sql.SQL('ANALYZE {}').format(sql.Identifier(table)))


def query_samples(conn,statement,params,count=20):
    durations=[]
    rows=0
    for number in range(count+1):
        started=time.perf_counter()
        result=conn.execute(statement,params).fetchall()
        if number:
            durations.append((time.perf_counter()-started)*1000)
        rows=len(result)
    plan=conn.execute('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) '+statement,params).fetchone()[0]
    return {'warm':distribution(durations),'returned_rows':rows,'plan':plan}


def idle_sql_load(dsn,users,seconds,pool_size=8):
    local=threading.local()
    connections=[]
    lock=threading.Lock()
    def execute(due):
        if not hasattr(local,'conn'):
            local.conn=psycopg.connect(dsn,autocommit=True,prepare_threshold=None,options='-c statement_timeout=3000')
            with lock:
                connections.append(local.conn)
        started=time.perf_counter()
        try:
            local.conn.execute(PAGE_SQL,(0,)).fetchall()
            finished=time.perf_counter()
            return ((finished-due)*1000,(finished-started)*1000,None)
        except Exception as exc:
            return ((time.perf_counter()-due)*1000,0,type(exc).__name__)
    futures=[]
    began=time.perf_counter()
    try:
        with ThreadPoolExecutor(max_workers=pool_size) as executor:
            for index in range(int(users*seconds/5)):
                due=began+index*5/users
                time.sleep(max(0,due-time.perf_counter()))
                futures.append(executor.submit(execute,due))
            results=[future.result() for future in futures]
    finally:
        for conn in connections:
            conn.close()
    elapsed=time.perf_counter()-began
    errors=defaultdict(int)
    for _,_,error in results:
        if error:
            errors[error]+=1
    return {'virtual_idle_users':users,'poll_interval_seconds':5,'scheduled_seconds':seconds,
            'offered_page_queries_per_second':users/5,'completed':len(results),'errors':dict(errors),
            'elapsed_seconds':round(elapsed,3),'completed_per_second':round(len(results)/elapsed,3),
            'scheduled_to_complete':distribution([r[0] for r in results]),
            'sql_execution':distribution([r[1] for r in results if not r[2]]),
            'sql_pool_size':pool_size,
            'limits':'One notification page per poll only; no ORM, HTTP, browser, authorization or full-history sweep. Not a 5000-session application test.'}


def run(customers,seconds):
    output={'started_utc':datetime.now(timezone.utc).isoformat(),'synthetic_customers':customers,
            'production_capacity_approved':False}
    with isolated_database() as (name,dsn):
        output['isolated_database']=name
        print('Measuring isolated queue stages',flush=True)
        output['queue']=queue_stages(dsn)
        print('Seeding isolated scale model',flush=True)
        with psycopg.connect(dsn,autocommit=True,prepare_threshold=None,options='-c statement_timeout=60000') as conn:
            began=time.perf_counter()
            seed(conn,customers)
            output['seed_seconds']=round(time.perf_counter()-began,3)
            output['database_bytes']=conn.execute('SELECT pg_database_size(current_database())').fetchone()[0]
            output['queries']={
                'notification_first_page':query_samples(conn,PAGE_SQL,(0,)),
                'notification_last_page':query_samples(conn,PAGE_SQL,(max(0,customers-51),)),
                'customer_exact_phone':query_samples(conn,'SELECT id FROM scale_customer WHERE company_id=1 AND branch_id=1 AND phone=%s LIMIT 50',(str(customers-1).zfill(13),)),
                'customer_substring_name':query_samples(conn,'SELECT id FROM scale_customer WHERE company_id=1 AND branch_id=1 AND name ILIKE %s LIMIT 50',('%'+str(customers-1)+'%',)),
            }
            cursor=0
            began=time.perf_counter()
            pages=0
            while pages<200:
                rows=conn.execute(PAGE_SQL,(cursor,)).fetchall()
                if not rows:
                    break
                cursor=rows[min(49,len(rows)-1)][0]
                pages+=1
                if len(rows)<=50:
                    break
            output['history_sweep']={'sampled_pages':pages,'sampled_conversations':cursor,
                'sample_elapsed_ms':round((time.perf_counter()-began)*1000,3),
                'full_sweep_pages_if_all_visible':math.ceil(customers/50),
                'limits':'SQL-only sampled pages; actual notifications also performs permissions, linking, unread and acknowledgement queries.'}
            print('Measuring synthetic substring index candidate',flush=True)
            conn.execute('CREATE EXTENSION pg_trgm')
            began=time.perf_counter()
            conn.execute('CREATE INDEX scale_customer_name_trgm ON scale_customer USING gin (name gin_trgm_ops)')
            output['candidate_trigram_index_build_seconds']=round(time.perf_counter()-began,3)
            conn.execute('ANALYZE scale_customer')
            output['queries']['customer_substring_name_with_trigram']=query_samples(conn,
                'SELECT id FROM scale_customer WHERE company_id=1 AND branch_id=1 AND name ILIKE %s LIMIT 50',
                ('%'+str(customers-1)+'%',))
            output['sql_prepare_threshold']=None
        output['idle_load']=[]
        for users in (100,1000,5000):
            print('Measuring SQL-only virtual idle users:',users,flush=True)
            output['idle_load'].append(idle_sql_load(dsn,users,seconds))
    output['isolated_database_removed']=True
    output['finished_utc']=datetime.now(timezone.utc).isoformat()
    return output


def main():
    logging.disable(logging.CRITICAL)
    parser=argparse.ArgumentParser()
    parser.add_argument('--customers',type=int,default=500000)
    parser.add_argument('--seconds',type=int,default=10)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    if not 100<=args.customers<=500000 or not 5<=args.seconds<=20:
        parser.error('Bounded isolated model: 100–500000 customers and 5–20 seconds per idle tier')
    try:
        output=run(args.customers,args.seconds)
        write_result(args.output,output)
    except Exception as exc:
        print(json.dumps({'error_category':type(exc).__name__}),file=sys.stderr)
        raise SystemExit(1) from None
    print(json.dumps({'output':args.output,'isolated_database_removed':True}))


if __name__=='__main__':
    main()
