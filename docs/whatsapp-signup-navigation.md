# WhatsApp signup visibility diagnosis

Date: 2026-11-16.

Reproduced on the live ecommerce instance: a direct signup-page load initialized
WhatsApp correctly, while login → Create account replaced the authentication card
without starting its new button interaction. The button existed in the returned
HTML but retained `d-none`; only the original Telegram control worked.

The correction is confined to `ab_storefront_whatsapp_auth`. Its interaction now
uses the persistent authentication-page root, delegates only WhatsApp events and
observes inserted form content to restore visibility for prefilled identities.
Existing storefront and Telegram source implementations were left unchanged.

Validation:

- 26 addon tests passed, zero failures/errors, on `wa_auth_test_20261115`.
- New browser regression covers login → signup, phone visibility, keyboard focus
  and interception of the correct WhatsApp form submission without sending a code.
- Existing direct signup, Arabic, recovery, permission and challenge tests passed.
- Test log: `/tmp/wa-auth-signup-navigation-final.log`.
- Live targeted upgrade log: `/tmp/wa-auth-signup-live-fix.log`.
- Live browser verification: login → signup, ready marker true, WhatsApp visible,
  positioned directly after the original verification button.
- User confirmed availability at `/web/signup?redirect=%2Fshop`.
- No additional live authentication messages were sent during diagnosis.

Files changed in the new addon: `static/src/js/signup.js`, `tests/test_http.py`,
`changelog.d/current.md`. No new user-facing strings were introduced.

Meta pricing was checked on its official calculator for Egypt / USD /
Authentication: standard list rate $0.0036 per delivered message, or $3.60 per
1,000. Delivered recovery codes and resends also count. Account eligibility for
higher authentication-international rates, tax and billing currency can affect
the actual invoice; account billing classification was not audited.

Sources:

- [Meta pricing and calculator](https://whatsappbusiness.com/products/platform-pricing/?country=Egypt&currency=US%20Dollars%20(USD)&category=Authentication)
- [Meta developer pricing documentation](https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing)
