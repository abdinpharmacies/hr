import httpx
import pytest

from app.providers import send
from test_gateway import telegram, whatsapp


def operation(**changes):
    return dict(
        {
            'destination': '12345',
            'body': 'Searchable branch evidence',
            'location': {
                'latitude': 0,
                'longitude': 180,
                'name': 'Branch',
                'address': 'Street',
            },
        },
        **changes
    )


def test_native_venue_payload_and_receipt():
    account = telegram().model_copy(update={'location_enabled': True})
    calls = []

    def transport(request):
        import json

        calls.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={'ok': True, 'result': {'message_id': 42}})

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        result = send(client, account, operation(reply_reference='12'))
    assert result == {'status': 'accepted', 'reference': '42', 'error': 'none'}
    assert calls[0][0].endswith('/sendVenue')
    assert calls[0][1] == {
        'chat_id': '12345',
        'latitude': 0,
        'longitude': 180,
        'title': 'Branch',
        'address': 'Street',
        'reply_parameters': {'message_id': 12},
    }


@pytest.mark.parametrize(
    'changes',
    [
        {'location': None},
        {'location': {}},
        {'location': {'latitude': True, 'longitude': 0}},
        {'media': [{}]},
        {'reaction': '👍'},
        {'contact_button': 'Contact'},
        {'template': {}, 'location': []},
        {'location': {'latitude': 91, 'longitude': 0, 'name': 'A', 'address': 'B'}},
        {
            'location': {
                'latitude': 0,
                'longitude': float('nan'),
                'name': 'A',
                'address': 'B',
            }
        },
        {'location': {'latitude': 0, 'longitude': 0, 'name': '', 'address': 'B'}},
    ],
)
def test_invalid_venue_never_calls_provider(changes):
    account = telegram().model_copy(update={'location_enabled': True})
    with httpx.Client(
        transport=httpx.MockTransport(lambda r: pytest.fail('Unexpected provider call'))
    ) as client:
        assert send(client, account, operation(**changes))['status'] == 'failed'


@pytest.mark.parametrize(
    'account', [telegram(), whatsapp().model_copy(update={'location_enabled': True})]
)
def test_disabled_and_whatsapp_fail_closed(account):
    with httpx.Client(
        transport=httpx.MockTransport(lambda r: pytest.fail('Unexpected provider call'))
    ) as client:
        assert send(client, account, operation())['status'] == 'failed'


@pytest.mark.parametrize(
    'failure,expected', [(httpx.ReadTimeout, 'review'), (httpx.ConnectError, 'failed')]
)
def test_venue_transport_uncertainty(failure, expected):
    def transport(request):
        raise failure('Synthetic failure', request=request)

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        assert (
            send(
                client,
                telegram().model_copy(update={'location_enabled': True}),
                operation(),
            )['status']
            == expected
        )
