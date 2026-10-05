import time


def run(environment):
    telegram = environment['ab_storefront_auth_telegram'].sudo()
    params = environment['ir.config_parameter'].sudo()
    if params.get_param('ab_storefront_auth.development', 'False') != 'True' or not telegram._enabled():
        raise SystemExit('Development polling requires development mode and securely configured Telegram credentials.')
    if telegram._api('getWebhookInfo', {}).get('url'):
        raise SystemExit('This bot already has a webhook. Development polling was not started.')
    environment.cr.commit()
    print('Storefront Telegram development receiver started.', flush=True)
    while True:
        try:
            environment.invalidate_all()
            if params.get_param('ab_storefront_auth.development', 'False') != 'True' or not telegram._enabled():
                environment.cr.rollback()
                print('Storefront Telegram development receiver stopped after configuration was disabled.', flush=True)
                break
            telegram._poll_once()
            environment['ab_storefront_auth_service'].sudo()._process_queue()
            environment.cr.commit()
        except KeyboardInterrupt:
            environment.cr.rollback()
            break
        except Exception:
            if environment.cr.closed:
                print('Telegram development receiver lost its database connection and will restart.', flush=True)
                raise
            environment.cr.rollback()
            print('Telegram development receiver will retry after a processing failure.', flush=True)
        time.sleep(2)


if 'env' in globals():
    run(globals()['env'])
