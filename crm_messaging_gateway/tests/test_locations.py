import copy

import pytest

from app.providers import normalize
from test_gateway import telegram, whatsapp, update


def telegram_location(value, venue=False):
    payload = update()
    del payload['message']['text']
    payload['message']['venue' if venue else 'location'] = value
    return payload


@pytest.mark.parametrize('latitude,longitude', [(0, 0), (-90, -180), (90, 180), (30.123, 31.456)])
def test_location_coordinates_and_identity(latitude, longitude):
    payload = telegram_location({'latitude': latitude, 'longitude': longitude})
    event = normalize(telegram(), payload)[0][2]
    assert event['location']['latitude'] == latitude
    assert event['location']['longitude'] == longitude
    assert event['unsupported'] is False
    assert f'{latitude}, {longitude}' in event['body']
    assert event == normalize(telegram(), copy.deepcopy(payload))[0][2]
    changed = copy.deepcopy(payload)
    changed['message']['location']['name'] = 'Place'
    assert normalize(telegram(), changed)[0][2]['source_digest'] != event['source_digest']


@pytest.mark.parametrize('value', [None, [], {}, {'latitude': True, 'longitude': 0},
    {'latitude': '0', 'longitude': 0}, {'latitude': 91, 'longitude': 0},
    {'latitude': 0, 'longitude': -181}, {'latitude': float('nan'), 'longitude': 0},
    {'latitude': float('inf'), 'longitude': 0}, {'latitude': 10**500, 'longitude': 0},
    {'latitude': 0, 'longitude': 0, 'name': []}])
def test_malformed_location_falls_back(value):
    event = normalize(telegram(), telegram_location(value))[0][2]
    assert event['unsupported'] is True
    assert 'location' not in event


def test_venue_live_snapshot_limits_and_edited_updates():
    event = normalize(telegram(), telegram_location({'location': {'latitude': 0, 'longitude': 0},
        'title': 'A' * 300, 'address': 'B' * 1100}, venue=True))[0][2]
    assert len(event['location']['name']) == 256
    assert len(event['location']['address']) == 1024
    payload = telegram_location({'latitude': 0, 'longitude': 0, 'live_period': 900})
    live = normalize(telegram(), payload)[0][2]
    assert live['location']['is_live_snapshot']
    assert live['body'].startswith('Location snapshot')
    payload['edited_message'] = payload.pop('message')
    payload['edited_message'].update(edit_date=1700000060, **{'from': {'id': 1234}})
    edited = normalize(telegram(), payload)[0][2]
    assert edited['edit']['reference'] == '2'
    assert edited['location']['is_live_snapshot']


@pytest.mark.parametrize('valid', [True, False])
def test_whatsapp_location(valid):
    message = {'id': 'wamid.location', 'from': '201012345678', 'timestamp': '1700000000',
               'type': 'location', 'location': {'latitude': 0 if valid else 100, 'longitude': 0}}
    payload = {'object': 'whatsapp_business_account', 'entry': [{'changes': [
        {'field': 'messages', 'value': {'metadata': {'phone_number_id': '456'}, 'messages': [message]}}
    ]}]}
    event = normalize(whatsapp(), payload)[0][2]
    assert event['unsupported'] is not valid
    assert ('location' in event) is valid
    if valid:
        assert event['location']['is_live_snapshot'] is False
