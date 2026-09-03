Current changes before commit:

- Allow backend login redirects to use normal Odoo admin/email usernames instead of forcing Egyptian phone-number validation.
- Keep the backend login field visually consistent with the storefront phone-login field while still accepting admin/email credentials.
- Keep backend login errors on the normal Odoo message path instead of replacing them with phone-login copy.
- Add a website compatibility method required by the current database layout template.
- Redirect customer logins to the storefront home page instead of the portal profile.
- Let username/email credentials such as `admin` pass through the storefront login form and redirect internal users to `/odoo`.
- Send customers to the profile page only on their first storefront login, then send later logins to home.

Files changed:

- `ab_ecommerce_storefront/controllers/auth.py`
- `ab_ecommerce_storefront/models/website.py`
- `ab_ecommerce_storefront/models/res_partner.py`
- `ab_ecommerce_storefront/views/auth.xml`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/changelog.d/current.md`
