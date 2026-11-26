import argparse
import json
import os
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from app.config import Settings


def prepare_config(path, base_code, target_code, source, apply=False):
    path = Path(path)
    original_stat = path.stat()
    if stat.S_IMODE(original_stat.st_mode) & 0o077:
        raise ValueError('The gateway configuration must be private')
    original = path.read_bytes()
    data = json.loads(original)
    try:
        Settings.model_validate(data)
    except Exception:
        raise ValueError('Gateway validation failed; private configuration details are withheld') from None
    base = data['accounts'][base_code]
    if base.get('provider') != 'website' or str(UUID(source)) != source or base_code == target_code:
        raise ValueError('Invalid Website connection')
    if base['provider_account'] == source:
        raise ValueError('The existing account already uses the requested source')
    existing = data['accounts'].get(target_code)
    if existing:
        if (existing.get('provider') != 'website' or existing.get('provider_account') != source
                or existing.get('website_url') != base.get('website_url')
                or existing.get('website_database') != base.get('website_database')):
            raise ValueError('The target code already belongs to another source')
        return {'account_code': target_code, 'source': source, 'created': False,
                'enabled': existing.get('enabled', False),
                'sending_enabled': existing.get('sending_enabled', False)}
    data['accounts'][target_code] = dict(base, provider_account=source, enabled=False, sending_enabled=False)
    try:
        Settings.model_validate(data)
    except Exception:
        raise ValueError('Gateway validation failed; private configuration details are withheld') from None
    backup = None
    if apply:
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup = path.with_name(path.name + '.before-website-connection-' + stamp)
        descriptor = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'wb') as target:
            target.write(original)
        descriptor, temporary = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
        try:
            with os.fdopen(descriptor, 'w') as target:
                os.fchmod(target.fileno(), stat.S_IMODE(original_stat.st_mode))
                if os.geteuid() == 0:
                    os.fchown(target.fileno(), original_stat.st_uid, original_stat.st_gid)
                json.dump(data, target, indent=2)
                target.write('\n')
                target.flush()
                os.fsync(target.fileno())
            if path.read_bytes() != original:
                raise ValueError('Configuration changed during preparation; nothing was replaced')
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return {'account_code': target_code, 'source': source, 'created': bool(apply),
            'enabled': False, 'sending_enabled': False, 'existing_accounts_unchanged': True,
            'backup': str(backup) if backup else None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--base-account', default='website-production')
    parser.add_argument('--account', default='website-production-reinstalled')
    parser.add_argument('--source', default='62c18ac9-3a5b-472d-a75c-86d8edb575f5')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    print(json.dumps(prepare_config(args.config, args.base_account, args.account, args.source,
        apply=args.apply), indent=2))
