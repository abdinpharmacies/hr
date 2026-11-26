import logging
import time
from .odoo import Odoo, OdooUnavailable

import httpx

from .config import settings, load_odoo_tokens
from .providers import send, send_read_receipt
from .observability import latency
from .media import download, MediaDependencyUnavailable
from .storage import Store


class Worker:
    def __init__(self, config, store, odoo, client, accounts=None):
        self.config, self.store, self.odoo, self.client = config, store, odoo, client
        self._schedule_position = 0
        self._receipt_position = 0
        self._report_position = 0
        self.accounts = list(config.accounts) if accounts is None else list(accounts)
        if set(self.accounts) - config.accounts.keys():
            raise ValueError("Unknown worker account")

    def ingest(self):
        row = self.store.claim_incoming(self.accounts)
        if not row:
            return
        success = False
        try:
            if row['kind'] == 'incoming' and row['payload'].get('edit'):
                try:
                    capabilities = self.odoo.call('get_capabilities', row['account'])
                except (RuntimeError, OdooUnavailable):
                    capabilities = {}
                if not isinstance(capabilities, dict) or not capabilities.get('message_edits'):
                    self.store.defer_incoming(row)
                    return True
            method = 'receive_event' if row['kind'] == 'incoming' else 'receive_status'
            values = (
                {'event': row['payload']}
                if row['kind'] == 'incoming'
                else row['payload']
            )
            result = self.odoo.call(method, row['account'], **values)
            if row['kind'] == 'incoming' and row['payload'].get('media') and not (
                isinstance(result, dict) and result.get('media_required') is False
            ):
                account = self.config.accounts[row['account']]
                if account.token is None:
                    load_odoo_tokens(self.config, self.odoo, accounts=[row['account']])
                try:
                    data = download(self.client, account, row['payload']['media'])
                except ValueError:
                    self.odoo.call(
                        'receive_media',
                        row['account'],
                        event_id=row['payload']['id'],
                        data='',
                        failed='limit',
                    )
                except httpx.HTTPError:
                    if row.get('attempts', 0) < 8:
                        raise
                    self.odoo.call(
                        'receive_media',
                        row['account'],
                        event_id=row['payload']['id'],
                        data='',
                        failed='download',
                    )
                else:
                    try:
                        self.odoo.call(
                            'receive_media',
                            row['account'],
                            event_id=row['payload']['id'],
                            data=data,
                            failed='',
                        )
                    except OdooUnavailable:
                        raise
                    except RuntimeError:
                        self.odoo.call(
                            'receive_media',
                            row['account'],
                            event_id=row['payload']['id'],
                            data='',
                            failed='invalid',
                        )
            success = True
        except MediaDependencyUnavailable:
            logging.warning('Incoming media deferred category=codec_unavailable')
            self.store.defer_incoming(row)
            return True
        except OdooUnavailable:
            self.store.defer_incoming(row)
            return True
        except Exception:
            pass
        self.store.finish_incoming(row, success)
        return True

    def collect(self, code):
        if code not in self.accounts:
            return
        account = self.config.accounts[code]
        if not self.config.sending_enabled or not account.enabled or not account.sending_enabled:
            return
        payload = self.odoo.call('lease_outgoing', code)
        if not payload:
            return
        account = self.config.accounts[code]
        if (
            payload['provider'] != account.provider
            or payload['provider_account'] != account.provider_account
        ):
            raise RuntimeError('Outgoing account mismatch')
        row = self.store.persist_outgoing(code, payload)
        self.odoo.call(
            'acknowledge_receipt',
            code,
            token=payload['token'],
            attempt=payload['attempt'],
            lease=payload['lease'],
            receipt=row['receipt'],
        )
        self.store.mark_ready(row)
        return True

    def recover_receipts(self):
        rows = self.store.stored(self.accounts)
        if not rows:
            return False
        position = self._receipt_position % len(rows)
        self._receipt_position = position + 1
        for row in rows[position:position + 1]:
            try:
                self.odoo.call(
                    'acknowledge_receipt',
                    row['account'],
                    token=row['token'],
                    attempt=row['attempt'],
                    lease='',
                    receipt=row['receipt'],
                )
                self.store.mark_ready(row)
                return True
            except Exception:
                pass

    def _send_operation(self, row):
        return send(self.client, self.config.accounts[row['account']], row['payload'])

    def dispatch(self):
        if not self.config.sending_enabled:
            return
        accounts = [
            code for code, account in self.config.accounts.items() if code in self.accounts and account.enabled and account.sending_enabled
        ]
        row = self.store.claim_outgoing(accounts)
        if row:
            try:
                allowed = self.odoo.call(
                    'authorize_send',
                    row['account'],
                    token=row['token'],
                    attempt=row['attempt'],
                    receipt=row['receipt'],
                )
            except Exception:
                allowed = False
            if isinstance(allowed, dict):
                if (
                    allowed.get('allowed') is False
                    and allowed.get('terminal') is True
                    and allowed.get('error') in ('window', 'rejected')
                ):
                    self.store.outcome(
                        row,
                        {
                            'status': 'failed',
                            'reference': '',
                            'error': allowed['error'],
                        },
                    )
                    return True
                allowed = False
            if not allowed:
                self.store.defer_send(row)
                return True
            with latency('provider_dispatch'):
                outcome = self._send_operation(row)
            self.store.outcome(row, outcome)
            return True

    def report(self):
        rows = self.store.reports(self.accounts)
        if not rows:
            return False
        position = self._report_position % len(rows)
        self._report_position = position + 1
        for row in rows[position:position + 1]:
            try:
                evidence = {
                    key: row['outcome'][key] for key in ('status', 'reference', 'error')
                }
                self.odoo.call(
                    'report_delivery',
                    row['account'],
                    token=row['token'],
                    attempt=row['attempt'],
                    receipt=row['receipt'],
                    **evidence
                )
                self.store.reported(row)
                return True
            except Exception:
                logging.warning('Delivery evidence pending for operation %s', row['id'])

    def read_receipts(self, code):
        if code not in self.accounts:
            return
        account = self.config.accounts[code]
        if not self.config.sending_enabled or account.provider != 'whatsapp' or not account.enabled:
            return
        payload = self.odoo.call('lease_read_receipt', code)
        if not payload:
            return
        if payload['provider'] != account.provider or payload['provider_account'] != account.provider_account:
            raise RuntimeError('Read receipt account mismatch')
        row = self.store.persist_read_receipt(code, payload)
        if account.token is None:
            load_odoo_tokens(self.config, self.odoo, accounts=[code])
        outcome = row['result_status'] or send_read_receipt(self.client, account, row['reference'])
        self.store.finish_read_receipt(code, payload['token'], outcome)
        self.odoo.call('report_read_receipt', code, token=payload['token'], lease=payload['lease'], status=outcome)
        return True

    def _cycle_operations(self):
        operations = [self.ingest, self.report, self.recover_receipts]
        for code in self.accounts:
            operations.append(lambda code=code: self.read_receipts(code))
            if self.config.sending_enabled:
                operations.append(lambda code=code: self.collect(code))
        if self.config.sending_enabled:
            operations.append(self.dispatch)
        return operations

    def tick(self):
        started = time.monotonic()
        self.store.recover_sending(self.accounts)
        operations = self._cycle_operations()
        completed = 0
        idle = 0
        for _ in range(25):
            if time.monotonic() - started >= 0.250:
                break
            operation = operations[self._schedule_position % len(operations)]
            self._schedule_position = (self._schedule_position + 1) % len(operations)
            try:
                progress = bool(operation())
            except Exception:
                logging.warning('Messaging operation deferred')
                progress = False
            completed += int(progress)
            idle = 0 if progress else idle + 1
            if idle >= len(operations):
                break
        return completed


def main(provider=None):
    config = settings(load_provider_tokens=False)
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.CRITICAL)
    logging.getLogger('httpcore').setLevel(logging.CRITICAL)
    accounts = [code for code, account in config.accounts.items()
                if account.provider != 'website' and (not provider or account.provider == provider)]
    with httpx.Client(timeout=20, follow_redirects=False) as client:
        if config.sending_enabled:
            load_odoo_tokens(config, Odoo(config, client), accounts=accounts)
        worker = Worker(
            config,
            Store(config.database_url.get_secret_value()),
            Odoo(config, client),
            client,
            accounts=accounts,
        )
        while True:
            try:
                progress = worker.tick()
            except Exception:
                logging.warning('Messaging worker cycle deferred')
                progress = 0
            if not progress:
                time.sleep(1)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--provider', choices=['telegram', 'whatsapp'])
    main(parser.parse_args().provider)
