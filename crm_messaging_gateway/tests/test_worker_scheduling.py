from unittest.mock import Mock

import pytest

from app.config import Account, Settings
from app.worker import Worker
from app.website import select_accounts


def configuration():
    return Settings(database_url='postgresql://localhost/synthetic_test',
        odoo_url='https://odoo.invalid', odoo_database='synthetic', odoo_key='test-key',
        accounts={'pilot': Account(provider='website', provider_account='00000000-0000-4000-8000-000000000001',
            website_url='https://shop.invalid', website_database='synthetic',
            odoo_key='test-key', token='test-key', reception='disabled', enabled=True)})


def test_eligible_backlog_uses_bounded_fair_cycles():
    worker = Worker(configuration(), Mock(), Mock(), Mock())
    operations = []
    worker.ingest = lambda: operations.append('ingest') or True
    worker.report = lambda: operations.append('report') or True
    worker.recover_receipts = lambda: operations.append('recover') or True
    worker.read_receipts = lambda code: operations.append(code) or True
    assert worker.tick() == 25
    assert len(operations) == 25
    assert set(operations) == {'ingest', 'report', 'recover', 'pilot'}
    worker.tick()
    assert operations[25] == 'report'


def test_idle_cycle_stops_after_one_round():
    worker = Worker(configuration(), Mock(), Mock(), Mock())
    worker.ingest = Mock(return_value=False)
    worker.report = Mock(return_value=False)
    worker.recover_receipts = Mock(return_value=False)
    worker.read_receipts = Mock(return_value=False)
    assert worker.tick() == 0
    worker.ingest.assert_called_once()
    worker.report.assert_called_once()


def test_slow_operation_yields_at_quantum_boundary(monkeypatch):
    worker = Worker(configuration(), Mock(), Mock(), Mock())
    clock = iter([0, 0, 0.3])
    monkeypatch.setattr('app.worker.time.monotonic', lambda: next(clock))
    worker.ingest = Mock(return_value=True)
    worker.report = Mock(return_value=True)
    assert worker.tick() == 1
    worker.report.assert_not_called()


def test_website_selection_rejects_wrong_disabled_and_duplicate_accounts():
    config = configuration()
    assert select_accounts(config, ['pilot']) == ['pilot']
    for accounts in (['unknown'], ['pilot', 'pilot']):
        with pytest.raises(ValueError):
            select_accounts(config, accounts)
    config.accounts['pilot'].enabled = False
    with pytest.raises(ValueError):
        select_accounts(config, ['pilot'])


def test_failed_delivery_report_does_not_starve_next_evidence():
    store, odoo = Mock(), Mock()
    first = dict(id=1, account='pilot', token='one', attempt=1, receipt='first',
                 outcome={'status': 'accepted', 'reference': 'one', 'error': 'none'})
    second = dict(first, id=2, token='two')
    store.reports.return_value = [first, second]
    odoo.call.side_effect = [RuntimeError('unavailable'), True]
    worker = Worker(configuration(), store, odoo, Mock())
    assert not worker.report()
    assert worker.report()
    store.reported.assert_called_once_with(second)


def test_deferred_incoming_does_not_delay_next_eligible_item():
    from app.odoo import OdooUnavailable
    first = {'account': 'pilot', 'kind': 'incoming', 'payload': {}}
    second = dict(first, id=2)
    store, odoo = Mock(), Mock()
    store.claim_incoming.side_effect = [first, second, None]
    store.reports.return_value = []
    store.stored.return_value = []
    odoo.call.side_effect = [OdooUnavailable('unavailable'), {'received': True}]
    worker = Worker(configuration(), store, odoo, Mock())
    assert worker.tick() == 2
    store.defer_incoming.assert_called_once_with(first)
    store.finish_incoming.assert_called_once_with(second, True)


@pytest.mark.parametrize('field', ['worker_idle_seconds', 'website_idle_seconds'])
@pytest.mark.parametrize('value', [0, 0.099, 2.01, float('inf'), float('nan')])
def test_worker_idle_configuration_is_bounded(field, value):
    values = configuration().model_dump()
    values[field] = value
    with pytest.raises(ValueError):
        Settings(**values)


def test_worker_idle_legacy_rollback_intervals():
    values = configuration().model_dump()
    assert Settings(**dict(values, worker_idle_seconds=1, website_idle_seconds=2))


def test_timing_correlations_are_opaque_and_destination_specific():
    from app.timing import correlation_id
    one = correlation_id('synthetic', '12345:1')
    assert len(one) == 32
    assert one == correlation_id('synthetic', '12345:1')
    assert one != correlation_id('synthetic', '67890:1')
    assert '12345' not in one
