from unittest.mock import Mock
import httpx
import pytest
from app.providers import normalize
from app.worker import Worker
from test_gateway import config, telegram, update


def edited_update(sequence=5):
    value = update(text='Changed')
    value['update_id'] = sequence
    value['edited_message'] = value.pop('message')
    value['edited_message'].update(edit_date=1700000060, **{'from': {'id': 1234}})
    return value


def test_edits_keep_message_reference_and_unique_update_identity():
    key, kind, event = normalize(telegram(), edited_update())[0]
    assert key == '5' and kind == 'incoming'
    assert event['id'] == 'edit:5' and event['edit']['reference'] == '2'
    assert event['edit']['sequence'] == 5
    assert event['body'] == 'Changed' and event['sender'] == '1234'
    assert event['edit']['date'] > event['timestamp']
    second = normalize(telegram(), edited_update(6))[0][2]
    assert second['id'] != event['id']
    assert second['edit']['reference'] == event['edit']['reference']


def test_invalid_edit_sender_date_and_nonprivate_chat():
    value = edited_update()
    value['edited_message']['from']['id'] = 999
    with pytest.raises(ValueError):
        normalize(telegram(), value)
    value = edited_update()
    value['edited_message']['edit_date'] = 1
    with pytest.raises(ValueError):
        normalize(telegram(), value)
    value = edited_update()
    value['edited_message']['chat']['type'] = 'group'
    assert normalize(telegram(), value)[0][1] == 'ignored'


@pytest.mark.parametrize('capabilities', [{}, {'message_edits': False}, RuntimeError('Old consumer')])
def test_edits_wait_durably_for_consumer_upgrade(capabilities):
    store, odoo = Mock(), Mock()
    store.claim_incoming.return_value = {'account': 'tg', 'kind': 'incoming', 'payload': normalize(telegram(), edited_update())[0][2]}
    if isinstance(capabilities, Exception):
        odoo.call.side_effect = capabilities
    else:
        odoo.call.return_value = capabilities
    Worker(config(), store, odoo, Mock()).ingest()
    store.defer_incoming.assert_called_once_with(store.claim_incoming.return_value)
    store.finish_incoming.assert_not_called()


def test_stale_or_unmatched_media_edits_do_not_download_files():
    store, odoo, client = Mock(), Mock(), Mock()
    event = normalize(telegram(), edited_update())[0][2]
    event['media'] = {'file_id': 'unused'}
    store.claim_incoming.return_value = {'account': 'tg', 'kind': 'incoming', 'payload': event}
    odoo.call.side_effect = [{'message_edits': True}, {'message_id': 1, 'media_required': False}]
    Worker(config(), store, odoo, client).ingest()
    client.post.assert_not_called()
    store.finish_incoming.assert_called_once_with(store.claim_incoming.return_value, True)

def test_polling_subscribes_to_and_persists_edits():
    from app.receiver import Receiver
    store, client, connection = Mock(), Mock(), Mock()
    store.polling_offset.return_value = 0
    client.post.return_value.status_code = 200
    client.post.return_value.json.return_value = {'ok': True, 'result': [edited_update()]}
    account = telegram().model_copy(update={'enabled': True, 'reception': 'polling'})
    assert Receiver('tg', account, store, client).tick(connection) == 1
    assert 'edited_message' in client.post.call_args.kwargs['json']['allowed_updates']
    events = store.persist_poll.call_args.args[3]
    assert events[0][2]['edit']['reference'] == '2'
    assert store.persist_poll.call_args.args[4] == 6
