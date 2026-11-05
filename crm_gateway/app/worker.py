import logging
import time
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select

from .config import settings
from .storage import Delivery, sessions, store_delivery

logger = logging.getLogger('crm_worker')


def rpc(peer, model, method, values):
    with httpx.Client(timeout=40, follow_redirects=False) as client:
        response = client.post(f'{peer.url}/json/2/{model}/{method}', json=values,
                               headers={'Authorization': 'Bearer ' + peer.key.get_secret_value(), 'X-Odoo-Database': peer.database})
        response.raise_for_status()
        return response.json()


def receive_messages(source, payload):
    config = settings().channels[source]
    messages = []
    if config.provider == 'telegram':
        msg = payload.get('message')
        if msg:
            messages.append((str(payload['update_id']), str(msg['chat']['id']), msg.get('text') or '[Attachment requires staff review]'))
    else:
        for entry in payload.get('entry', []):
            for change in entry.get('changes', []):
                value = change.get('value', {})
                if value.get('metadata', {}).get('phone_number_id') != config.phone_number_id:
                    raise ValueError('Provider account mismatch')
                for msg in value.get('messages', []):
                    messages.append((msg['id'], msg['from'], msg.get('text', {}).get('body') or '[Attachment requires staff review]'))
    for event_id, destination, body in messages:
        rpc(settings().odoo, 'ab_crm_gateway_api', 'receive_message',
            {'channel_code': source, 'event_id': event_id, 'external_key': destination, 'body': body})


def deliver_pending():
    now = datetime.now(timezone.utc)
    with sessions()() as session, session.begin():
        rows = session.scalars(select(Delivery).where(Delivery.state == 'pending', Delivery.next_attempt <= now).order_by(Delivery.created_at).limit(50).with_for_update(skip_locked=True)).all()
        for row in rows:
            try:
                if row.kind == 'message':
                    receive_messages(row.source, row.payload)
                elif row.kind == 'website':
                    rpc(settings().odoo, 'ab_oms_sync_event', 'receive_event', {'channel_code': row.source, 'event': row.payload})
                elif row.kind == 'website_update':
                    rpc(settings().website, 'ab_oms_website_event', 'receive_update', {'event': row.payload['event']})
                    rpc(settings().odoo, 'ab_oms_sync_update', 'acknowledge', {'ids': [row.payload['id']]})
                else:
                    continue
                row.state = 'delivered'
                row.error = None
                row.last_success = now
            except Exception as error:
                row.attempts += 1
                row.error = type(error).__name__
                row.next_attempt = now + timedelta(seconds=min(3600, 2 ** min(row.attempts, 12)))
                if row.attempts >= 12:
                    row.state = 'review'


def sync_website():
    if not settings().website:
        return
    events = rpc(settings().website, 'ab_oms_website_event', 'pending_events', {})
    for item in events:
        event = item['event']
        with sessions()() as session, session.begin():
            store_delivery(session, event['source'], event['event_id'], 'website', event)
        rpc(settings().website, 'ab_oms_website_event', 'acknowledge', {'ids': [item['id']]})
    for item in rpc(settings().odoo, 'ab_oms_sync_update', 'pending_updates', {}):
        with sessions()() as session, session.begin():
            store_delivery(session, 'oms:' + item['source'], item['event']['event_id'], 'website_update', item)


def send_reply():
    reply = rpc(settings().odoo, 'ab_crm_gateway_api', 'lease_reply', {})
    if not reply:
        return
    with sessions()() as session, session.begin():
        delivery = store_delivery(session, 'reply:' + reply['channel'], reply['token'], 'reply', reply)
        if delivery.state != 'pending':
            return
        delivery.state = 'unknown'
    config = settings().channels[reply['channel']]
    with httpx.Client(timeout=30, follow_redirects=False) as client:
        if config.provider == 'telegram':
            response = client.post(f'https://api.telegram.org/bot{config.token.get_secret_value()}/sendMessage',
                                   json={'chat_id': reply['destination'], 'text': reply['body']})
            response.raise_for_status()
            result = response.json()
            if not result.get('ok'):
                raise ValueError('Provider did not confirm delivery')
            reference = str(result['result']['message_id'])
        elif config.provider == 'whatsapp' and config.graph_version and config.phone_number_id:
            response = client.post(f'https://graph.facebook.com/{config.graph_version}/{config.phone_number_id}/messages',
                headers={'Authorization': 'Bearer ' + config.token.get_secret_value()},
                json={'messaging_product': 'whatsapp', 'to': reply['destination'], 'type': 'text', 'text': {'body': reply['body']}})
            response.raise_for_status()
            reference = response.json()['messages'][0]['id']
        else:
            raise ValueError('Provider configuration incomplete')
    with sessions()() as session, session.begin():
        delivery = session.get(Delivery, delivery.id)
        delivery.state = 'provider_confirmed'
        delivery.payload = dict(delivery.payload, provider_reference=reference)
    report_confirmed_replies()


def report_confirmed_replies():
    with sessions()() as session, session.begin():
        for row in session.scalars(select(Delivery).where(Delivery.kind == 'reply', Delivery.state == 'provider_confirmed').limit(50)):
            rpc(settings().odoo, 'ab_crm_gateway_api', 'report_reply', {'message_id': row.payload['id'], 'token': row.payload['token'], 'provider_reference': row.payload['provider_reference']})
            row.state = 'delivered'
            row.last_success = datetime.now(timezone.utc)


def deliver_submission():
    lease = rpc(settings().odoo, 'ab_oms_attempt', 'lease_submission', {})
    if lease:
        rpc(settings().odoo, 'ab_oms_attempt', 'deliver_submission', {'ids': [lease['id']], 'revision': lease['revision']})


def main():
    next_sync = 0
    while True:
        tasks = [deliver_pending, report_confirmed_replies, deliver_submission, send_reply]
        if time.monotonic() >= next_sync:
            tasks.insert(0, sync_website)
            next_sync = time.monotonic() + 60
        for task in tasks:
            try:
                task()
            except Exception as error:
                logger.warning('%s failed: %s', task.__name__, type(error).__name__)
        time.sleep(2)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    main()
