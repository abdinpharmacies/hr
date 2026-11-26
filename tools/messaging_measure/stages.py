import argparse
import configparser
import json
import math
import os
import ssl
import statistics
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx
import psycopg
from psycopg.rows import dict_row
from result_io import write_result


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'crm_messaging_gateway'))


def distribution(values):
    ordered = sorted(values)
    if not ordered:
        return {'samples': 0}
    def percentile(fraction):
        return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]
    return {'samples': len(ordered), 'min_ms': round(ordered[0], 3),
            'p50_ms': round(percentile(.5), 3), 'p95_ms': round(percentile(.95), 3),
            'p99_ms': round(percentile(.99), 3), 'max_ms': round(ordered[-1], 3),
            'mean_ms': round(statistics.mean(ordered), 3)}


def read_private(path):
    path = Path(path)
    if path.stat().st_mode & 0o077:
        raise ValueError('Private configuration permissions required')
    return json.loads(path.read_text())


def database_options():
    parser = configparser.RawConfigParser()
    if not parser.read('/opt/odoo19/conf/callcenter19.conf'):
        raise ValueError('Callcenter configuration unavailable')
    c = parser['options']
    return {'host': c['db_host'], 'port': c['db_port'], 'user': c['db_user'],
            'password': c['db_password'], 'connect_timeout': 5}


def probe(client, method, url, count, headers=None, body=None, expected=None):
    timings, header_timings, connection_timings = [], [], defaultdict(list)
    statuses, errors, versions = Counter(), Counter(), Counter()
    first = None
    for index in range(count):
        starts = {}
        response_headers_at = []
        began = time.perf_counter()
        def trace(event, info):
            now = time.perf_counter()
            if event.endswith('.started'):
                starts[event.removesuffix('.started')] = now
            if event.endswith('.complete'):
                name = event.removesuffix('.complete')
                if name in starts and ('connect_tcp' in name or 'start_tls' in name):
                    connection_timings[name].append((now - starts[name]) * 1000)
                if 'receive_response_headers' in name:
                    response_headers_at.append((now - began) * 1000)
        try:
            response = client.request(method, url, headers=headers, json=body,
                                      extensions={'trace': trace})
            elapsed = (time.perf_counter() - began) * 1000
            statuses[str(response.status_code)] += 1
            versions[response.http_version] += 1
            if expected is not None and response.status_code == 200:
                try:
                    if not expected(response.json()):
                        errors['unexpected_response_contract'] += 1
                except ValueError:
                    errors['invalid_json'] += 1
            if index == 0:
                first = round(elapsed, 3)
            else:
                timings.append(elapsed)
                header_timings.extend(response_headers_at)
            if response.status_code in (429, 503) or response.status_code >= 500:
                break
        except Exception as exc:
            errors[type(exc).__name__] += 1
            break
        time.sleep(.2)
    return {'first_request_ms': first, 'warm_total': distribution(timings),
            'warm_headers': distribution(header_timings), 'statuses': dict(statuses),
            'errors': dict(errors), 'http_versions': dict(versions),
            'connection_components': {k: distribution(v) for k, v in connection_timings.items()},
            'sampling': 'sequential, 200ms pause, stop on transport/server/rate-limit failure'}


def live(count):
    private = Path('/home/abdin_04/.config/crm-messaging')
    config = read_private(private / 'config.json')
    website = read_private(private / 'config-website-pilot.json')
    production = website['accounts']['website-production-reinstalled']
    ca = ssl.create_default_context()
    ca.load_verify_locations(str(private / 'website-pilot/tls/ca-bundle.crt'))
    result = {'mode': 'bounded_live_readonly_probes', 'started_utc': datetime.now(timezone.utc).isoformat(),
              'requested_samples_per_endpoint': count, 'probes': {}}
    with httpx.Client(timeout=httpx.Timeout(10, connect=5), verify=ca,
                      follow_redirects=False, trust_env=False) as client:
        for route in ('health', 'ready'):
            result['probes']['fastapi_' + route] = probe(
                client, 'GET', 'http://127.0.0.1:5088/' + route, count,
                expected=lambda value: value == {'status': 'ok'})
        for code, account in config['accounts'].items():
            payload = {'correlation_id': str(uuid4()), 'payload': {
                'account_code': code, 'provider_account': account['provider_account']}}
            result['probes']['callcenter_capabilities_' + account['provider']] = probe(
                client, 'POST', config['odoo_url'] + '/crm/messaging/v1/get_capabilities', count,
                headers={'Authorization': 'Bearer ' + (account.get('odoo_key') or config['odoo_key']),
                         'X-Odoo-Database': config['odoo_database']}, body=payload,
                expected=lambda value: isinstance(value.get('result'), dict))
        account = production
        result['probes']['callcenter_https_website_capabilities'] = probe(
            client, 'POST', website['odoo_url'] + '/json/2/ab_crm_messaging_api/website_capabilities', count,
            headers={'Authorization': 'Bearer ' + (account.get('odoo_key') or website['odoo_key']),
                     'X-Odoo-Database': website['odoo_database']},
            body={'account_code': 'website-production-reinstalled', 'provider_account': account['provider_account']},
            expected=lambda value: value == {'version': 4})
        result['probes']['production_website_v4_capabilities'] = probe(
            client, 'POST', account['website_url'] + '/storefront-callcenter/v4/capabilities', count,
            headers={'Authorization': 'Bearer ' + account['token'],
                     'X-Odoo-Database': account['website_database']},
            body={'source': account['provider_account']}, expected=lambda value: value == {'version': 4})
        result['probes']['production_website_login'] = probe(
            client, 'GET', account['website_url'] + '/web/login', min(count, 6))
    result['finished_utc'] = datetime.now(timezone.utc).isoformat()
    return result


def passive():
    config = read_private('/home/abdin_04/.config/crm-messaging/config.json')
    options = '-c default_transaction_read_only=on -c statement_timeout=5000'
    output = {'mode': 'passive_historical_local_timestamps', 'observed_utc': datetime.now(timezone.utc).isoformat()}
    with psycopg.connect(config['database_url'], options=options, row_factory=dict_row) as queue:
        incoming = queue.execute("""SELECT account,event_key,created_at,payload->>'id' AS provider_id,
            payload->>'timestamp' AS source_timestamp,payload->'website_event'->>'event_uuid' AS website_id
            FROM incoming_event WHERE kind='incoming' AND state='done' ORDER BY id DESC LIMIT 5000"""
        ).fetchall()
        outgoing = queue.execute('SELECT account,token,attempt,created_at FROM outgoing_operation ORDER BY id DESC LIMIT 5000').fetchall()
        output['queue_snapshot'] = queue.execute("""SELECT account,state,count(*) AS count,
            extract(epoch FROM now()-min(created_at)) AS oldest_age_seconds FROM incoming_event
            WHERE state NOT IN ('done','ignored') GROUP BY account,state""").fetchall()
        output['queue_database_bytes'] = queue.execute('SELECT pg_database_size(current_database()) AS bytes').fetchone()['bytes']
    with psycopg.connect(**database_options(), dbname='callcenter', options=options, row_factory=dict_row) as odoo:
        events = odoo.execute('''SELECT a.code,e.event_key,e.create_date FROM ab_crm_messaging_event e
            JOIN ab_crm_messaging_account a ON a.id=e.account_id''').fetchall()
        website_events = odoo.execute('''SELECT a.code,e.event_uuid,e.create_date FROM ab_crm_website_event e
            JOIN ab_crm_messaging_account a ON a.id=e.account_id''').fetchall()
        operations = odoo.execute('''SELECT a.code,o.token,o.attempt,o.create_date FROM ab_crm_messaging_operation o
            JOIN ab_crm_messaging_account a ON a.id=o.account_id''').fetchall()
        output['live_counts'] = {}
        for table in ('ab_crm_customer','ab_crm_conversation','ab_crm_message','ab_crm_website_event'):
            output['live_counts'][table] = odoo.execute('SELECT count(*) AS n FROM ' + table).fetchone()['n']
        output['callcenter_database_bytes'] = odoo.execute('SELECT pg_database_size(current_database()) AS bytes').fetchone()['bytes']
        output['database_version'] = odoo.execute('SHOW server_version').fetchone()['server_version']
        output['existing_indexes'] = odoo.execute("""SELECT tablename,indexdef FROM pg_indexes WHERE schemaname='public'
            AND tablename IN ('ab_crm_customer','ab_crm_conversation','ab_crm_message') ORDER BY tablename,indexname""").fetchall()
    event_map = {(r['code'],r['event_key']): r['create_date'].replace(tzinfo=timezone.utc) for r in events}
    website_map = {(r['code'],r['event_uuid']): r['create_date'].replace(tzinfo=timezone.utc) for r in website_events}
    operation_map = {(r['code'],r['token'],r['attempt']): r['create_date'].replace(tzinfo=timezone.utc) for r in operations}
    stages = defaultdict(list)
    negatives = Counter()
    for row in incoming:
        key = row['website_id'] or row['provider_id'] or row['event_key']
        arrived = (website_map if row['website_id'] else event_map).get((row['account'],key))
        if arrived:
            elapsed = (arrived-row['created_at']).total_seconds()*1000
            if elapsed >= 0:
                stages['queue_to_odoo_create_' + row['account']].append(elapsed)
            else:
                negatives[row['account']] += 1
        if row['source_timestamp']:
            try:
                origin = datetime.fromisoformat(row['source_timestamp']).replace(tzinfo=timezone.utc)
                elapsed = (row['created_at']-origin).total_seconds()*1000
                if elapsed >= 0:
                    stages['provider_timestamp_to_queue_' + row['account']].append(elapsed)
            except ValueError:
                pass
    for row in outgoing:
        created = operation_map.get((row['account'],row['token'],row['attempt']))
        if created:
            elapsed=(row['created_at']-created).total_seconds()*1000
            if elapsed>=0:
                stages['odoo_operation_to_queue_' + row['account']].append(elapsed)
    output['stages']={k:distribution(v) for k,v in stages.items()}
    output['negative_timestamp_pairs_excluded']=dict(negatives)
    output['limits']=['Historical, mixed ages and outages; not a controlled fresh-message benchmark.',
                      'Odoo create_date is not transaction commit time; provider timestamps may have one-second resolution.',
                      'No provider-acceptance timestamp, queue-completion timestamp or browser visibility timestamp is stored here.']
    return output


def journal():
    units=[('system','crm-messaging-callcenter.service'),('user','crm-messaging-pilot-telegram.service'),
           ('user','crm-messaging-pilot-whatsapp.service'),('user','crm-messaging-pilot-website.service'),
           ('user','crm-storefront-auth.service')]
    import re
    result={'mode':'sanitized_service_journal_metrics','observed_utc':datetime.now(timezone.utc).isoformat(),'units':{}}
    for manager,unit in units:
        command=['journalctl']+(['--user'] if manager=='user' else [])+[
            '-u',unit,'--since','24 hours ago','-n','5000','--no-pager','-o','cat']
        completed=subprocess.run(command,capture_output=True,text=True,timeout=10)
        durations=defaultdict(list)
        failures=Counter()
        for line in completed.stdout.splitlines():
            match=re.search(r'operation=([a-z_]+) elapsed_ms=([0-9.]+)',line)
            if match:
                durations[match[1]].append(float(match[2]))
            match=re.search(r'Website failure account=([\w-]+) phase=([\w-]+).*cause=([\w-]+)',line)
            if match:
                failures[':'.join(match.groups())]+=1
        result['units'][unit]={'exit_code':completed.returncode,
            'sample_lines':len(completed.stdout.splitlines()),
            'operations':{name:distribution(values) for name,values in durations.items()},
            'website_failure_categories':dict(failures)}
    return result


def website_fetch(count):
    private=Path('/home/abdin_04/.config/crm-messaging')
    config=read_private(private/'config-website-pilot.json')
    account=config['accounts']['website-production-reinstalled']
    result={'mode':'production_readonly_fetch_without_acknowledgement',
            'started_utc':datetime.now(timezone.utc).isoformat(),'probes':{}}
    with httpx.Client(timeout=httpx.Timeout(10,connect=5),follow_redirects=False,trust_env=False) as client:
        for version in (1,3,4,2):
            result['probes']['production_website_v'+str(version)+'_fetch']=probe(
                client,'POST',account['website_url']+f'/storefront-callcenter/v{version}/fetch',count,
                headers={'Authorization':'Bearer '+account['token'],'X-Odoo-Database':account['website_database']},
                body={'source':account['provider_account']},expected=lambda value:isinstance(value,list))
    result['finished_utc']=datetime.now(timezone.utc).isoformat()
    result['limits']='No event bodies are stored or printed. Events are not acknowledged, captured into Callcenter or sent.'
    return result


def providers(count):
    from app.config import Settings, load_odoo_tokens
    from app.odoo import Odoo
    import logging
    logging.getLogger('httpx').setLevel(logging.CRITICAL)
    config=Settings.model_validate(read_private('/home/abdin_04/.config/crm-messaging/config.json'))
    result={'mode':'provider_identity_readonly_probes','started_utc':datetime.now(timezone.utc).isoformat(),'probes':{}}
    with httpx.Client(timeout=10,follow_redirects=False,trust_env=False) as client:
        load_odoo_tokens(config,Odoo(config,client))
        for code,account in config.accounts.items():
            if account.provider=='telegram':
                result['probes']['telegram_get_me']=probe(client,'GET',
                    'https://api.telegram.org/bot'+account.token.get_secret_value()+'/getMe',count,
                    expected=lambda value:value.get('ok') is True and str(value.get('result',{}).get('id'))==account.provider_account)
            elif account.provider=='whatsapp':
                result['probes']['whatsapp_sender_identity']=probe(client,'GET',
                    'https://graph.facebook.com/'+account.graph_version+'/'+account.provider_account+'?fields=id',count,
                    headers={'Authorization':'Bearer '+account.token.get_secret_value()},
                    expected=lambda value:value.get('id')==account.provider_account)
    result['finished_utc']=datetime.now(timezone.utc).isoformat()
    result['limits']='Identity endpoints measure provider HTTP path, not actual message acceptance, delivery or read receipt.'
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=('live','passive','journal','website-fetch','providers'))
    parser.add_argument('--samples',type=int,default=16)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    if not 2<=args.samples<=30:
        parser.error('Use 2 to 30 sequential samples')
    try:
        runners={'live':lambda:live(args.samples),'passive':passive,'journal':journal,
                 'website-fetch':lambda:website_fetch(min(args.samples,8)),
                 'providers':lambda:providers(min(args.samples,10))}
        data=runners[args.mode]()
        write_result(args.output,data)
    except Exception as exc:
        print(json.dumps({'error_category':type(exc).__name__}),file=sys.stderr)
        raise SystemExit(1) from None
    print(json.dumps({'output':args.output,'mode':args.mode}))


if __name__=='__main__':
    main()
