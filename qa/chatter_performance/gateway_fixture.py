import argparse
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'crm_messaging_gateway'))

from app.config import Account, Settings
from app.storage import Store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--queue', type=Path, required=True)
    parser.add_argument('--origin', default='http://127.0.0.1:5085')
    args = parser.parse_args()
    fixture = json.loads(args.fixture.read_text())
    origin = urlsplit(args.origin)
    if (not fixture['database'].startswith('callcenter_timing_') or args.output.exists()
            or args.fixture.stat().st_mode & 0o077 or origin.hostname != '127.0.0.1'
            or origin.port is None or not 5069 <= origin.port <= 5099):
        parser.error('Use a private disposable fixture and an alternate loopback test port')
    os.umask(0o077)
    args.queue.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    settings = Settings(database_url='sqlite://' + str(args.queue.resolve()),
        encrypted_storage_confirmed=True, odoo_url=args.origin, allow_loopback_http=True,
        odoo_database=fixture['database'], odoo_key=fixture['odoo_key'], sending_enabled=False,
        accounts={'workspace-bot': Account(provider='telegram', provider_account='900000234',
            token_source='odoo', webhook_secret=fixture['webhook_secret'], enabled=True)})
    Store(settings.database_url.get_secret_value()).migrate()
    args.output.write_text(json.dumps(settings.model_dump(), default=lambda value: value.get_secret_value()))
    args.output.chmod(0o600)
    print('Private synthetic gateway configuration ready; provider sending disabled')


if __name__ == '__main__':
    main()
