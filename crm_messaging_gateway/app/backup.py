from datetime import datetime, timezone
import os
from pathlib import Path

from .config import settings
from .queue_transfer import backup_queue
from .storage import Store


def main():
    store = Store(settings(load_provider_tokens=False).database_url.get_secret_value())
    sqlite = store.database_url.startswith('sqlite:')
    directory = (store.path.parent if sqlite else Path(os.environ['CRM_MESSAGING_CONFIG']).parent) / 'backups'
    directory.mkdir(mode=0o700, exist_ok=True)
    if directory.stat().st_mode & 0o077:
        raise RuntimeError('The backup directory must be private')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    if sqlite:
        result = backup_queue(store, directory / ('queue-' + stamp + '.db'))
    else:
        from .postgres_backup import backup_postgres
        result = backup_postgres(store, directory / ('queue-' + stamp + '.dump'))
    print('Queue backup archive verified in %.3f seconds' % result['seconds'])


if __name__ == '__main__':
    main()
