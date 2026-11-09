import argparse
import configparser
import hmac
import json

from .config import settings


def consistency(account, host):
    values = host.get('options', {})
    return {
        'provider': account.provider == 'whatsapp',
        'dedicated_odoo_key_present': bool(account.odoo_key and account.odoo_key.get_secret_value()),
        'business_number_matches': hmac.compare_digest(account.provider_account, values.get('whatsapp_phone_number_id', '').strip()),
        'version_explicit_and_matches': account.graph_version == values.get('whatsapp_api_version', '').strip() == 'v26.0',
        'token_present_and_matches': bool(account.token and values.get('whatsapp_token')) and hmac.compare_digest(account.token.get_secret_value(), values.get('whatsapp_token', '').strip()),
        'signature_secret_present': bool(account.webhook_secret and len(account.webhook_secret.get_secret_value()) >= 16),
        'verification_token_present': bool(account.verify_token and account.verify_token.get_secret_value()),
        'sending_paused': not account.sending_enabled,
        'reception_paused': not account.enabled or account.reception == 'disabled',
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--odoo-config', required=True)
    parser.add_argument('--account', default='wa-callcenter')
    args = parser.parse_args()
    config = settings(load_provider_tokens=False)
    host = configparser.RawConfigParser()
    if not host.read(args.odoo_config):
        raise SystemExit('Host configuration is unavailable')
    account = config.accounts.get(args.account)
    if not account:
        raise SystemExit('WhatsApp account is not prepared')
    result = consistency(account, dict(host))
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if all(result.values()) else 1)


if __name__ == '__main__':
    main()
