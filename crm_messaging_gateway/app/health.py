import time


def age_seconds(value, now):
    if value is None:
        return None
    return max(0, now - (value.timestamp() if hasattr(value, 'timestamp') else float(value)))


def reception_health(config, polling, backlog, now=None):
    now = time.time() if now is None else now
    heartbeats = {row['provider_account']: row['updated_at'] for row in polling}
    oldest = {row['account']: row['oldest'] for row in backlog}
    result = {}
    for code, account in config.accounts.items():
        polling_enabled = account.enabled and account.provider == 'telegram' and account.reception == 'polling'
        age = age_seconds(heartbeats.get(account.provider_account), now) if polling_enabled else None
        result[code] = {
            'enabled': account.enabled,
            'reception': account.reception,
            'heartbeat_age_seconds': age,
            'healthy': age is not None and age <= 120 if polling_enabled else None,
            'backlog_age_seconds': age_seconds(oldest.get(code), now),
        }
    return result


def website_queue_health(rows, now=None):
    now = time.time() if now is None else now
    pending = [row for row in rows if row['state'] not in ('done', 'superseded')]
    blocked = {(row['account'], row['destination']) for row in rows
               if row.get('outcome_status') == 'review' and row['state'] != 'superseded'}
    return {
        'oldest_pending_age_seconds': max((age_seconds(row['created_at'], now) for row in pending), default=0),
        'blocked_streams': len(blocked),
        'retrying': sum(row['state'] == 'ready' and row['sends'] > 0 for row in rows),
    }
