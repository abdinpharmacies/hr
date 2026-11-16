# WhatsApp authentication activation

Completed 2026-11-16 on the local ecommerce instance (`e_commerce`).

## Result

- `ab_storefront_whatsapp_auth` is installed and its default-website transport is enabled.
- Meta approved `abdin_authentication_en` (`en_US`) and `abdin_authentication_ar` (`ar`), both AUTHENTICATION copy-code templates with a five-minute code expiry.
- Exactly one Arabic authentication message was sent to the user-authorized number ending in **3233**. Meta progressed through accepted, delivered and read. The send used one attempt.
- Delivery payload was cleared after provider acceptance. All three status receipts were processed through the authentication queue only; none entered staff conversation processing.
- No customer account was created by the pilot. The verification challenge expires normally.
- English and Arabic signup pages expose the WhatsApp verification button.
- The optional API and `ab_ecommerce_api_whatsapp` remain uninstalled because the customer API is unused, consistent with the implementation plan.
- Telegram's existing configuration was preserved. It remains disabled; either channel can independently verify the phone when configured.

Open the local secure signup page at <https://127.0.0.1:5443/web/signup>.

## Runtime configuration

- Native dedicated service account: XML ID `ab_storefront_whatsapp_auth.user_auth_worker`, provisioned through module-owned `security/service_user.xml` with minimal groups and the website company.
- Configured transport: XML ID `ab_storefront_whatsapp_auth.transport_default_website`.
- Worker configuration: private mode-0600 `/home/abdin_04/.config/crm-messaging/auth.json`. The API key is dedicated to the worker and expires 90 days after provisioning; rotate it before expiry. No credential is included in this report or source.
- Enabled user service: `crm-storefront-auth.service`, using verified HTTPS to ecommerce on port 5443. It was active with zero restarts during final verification.
- Existing managed receiver: `crm-messaging-callcenter.service`, now using `app.auth_receiver:create_app`. The user approved the native administrator prompt for its systemd override and restart. Both `/health` and `/ready` returned HTTP 200.
- Override: `/etc/systemd/system/crm-messaging-callcenter.service.d/whatsapp-authentication.conf`.
- The user's Odoo process was not stopped or restarted. Targeted module operations used `--stop-after-init --no-http --workers=0 --max-cron-threads=0 --http-port=5069 --gevent-port=5072`. Temporary validation ports were released.

## Verification and evidence

- Private PostgreSQL backup was created and verified before installation: `/tmp/ecommerce-before-whatsapp-activation-20261116.dump`.
- Install log: `/tmp/wa-auth-live-install-20261116.log`.
- Dedicated account/configuration upgrade: `/tmp/wa-auth-live-service-user-20261116.log`.
- Live worker direct ORM reads on challenges, events and transport configuration were all denied. The scoped native exchange authenticated correctly and rejected a disabled transport before enablement.
- The approved receiver factory passed health and durable-queue readiness checks before switching the service.
- Live signup pages were checked in English and Arabic through the running HTTPS proxy.
- The pilot reached `wa_read`, attempts `1`, provider reference present, encrypted payload cleared.

This pilot validates live template delivery and receipt routing. Signup, recovery, reset/session invalidation, browser binding and replay behavior were covered by the prior [implementation validation](whatsapp-authentication-validation.md); the pilot did not create a real customer account or reset a real customer's password.

## Source and rollback

Existing application logic remains untouched. Activation adds only the dedicated service-user security XML and its manifest registration in the new addon. Gateway switching was a systemd configuration override, not a modification to the old receiver source.

To suspend new WhatsApp authentication, disable the transport in Settings / WhatsApp Authentication and stop `crm-storefront-auth.service`. Keep the authentication-aware receiver running to isolate delayed receipts. Existing password login is unaffected.
