from datetime import datetime, timezone

from .config import settings
from .queue_transfer import backup_queue
from .storage import Store


def main():
    store = Store(settings(load_provider_tokens=False).database_url.get_secret_value())
    if not store.database_url.startswith('sqlite:'):
        raise RuntimeError('Scheduled backup requires a SQLite queue')
    directory = store.path.parent / 'backups'
    directory.mkdir(mode=0o700, exist_ok=True)
    if directory.stat().st_mode & 0o077:
        raise RuntimeError('The backup directory must be private')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    result = backup_queue(store, directory / ('queue-' + stamp + '.db'))
    print('SQLite backup verified in %.3f seconds' % result['seconds'])


if __name__ == '__main__':
    main()
