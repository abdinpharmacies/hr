Current changes before commit:

- Allow backend login redirects to use normal Odoo admin/email usernames instead of forcing Egyptian phone-number validation.
- Keep the backend login field visually consistent with the storefront phone-login field while still accepting admin/email credentials.
- Keep backend login errors on the normal Odoo message path instead of replacing them with phone-login copy.
- Add a website compatibility method required by the current database layout template.
- Redirect customer logins to the storefront home page instead of the portal profile.
- Let username/email credentials such as `admin` pass through the storefront login form and redirect internal users to `/odoo`.
- Send customers to the profile page only on their first storefront login, then send later logins to home.
- Remove the duplicated light input layer from the storefront search bar while keeping the custom search container stroke and Odoo search behavior.
- Make Tab move from the login phone field directly to the password field instead of the reset-password link.
- Keep login input text, caret direction, and placeholder aligned to the right for Arabic users.
- Move auth field icons to the left side of the input while preserving the existing form layout.
- Add a focused auth-field override asset so the active storefront keeps the corrected RTL input behavior even when stale duplicate static files exist elsewhere in the addons path.
- Prevent the login phone field validation shake when a user clicks Create Account with a partially entered phone number.
- Track whether the customer completed the avatar choice separately from the selected avatar value.
- Update the profile completion progress immediately after saving any avatar choice, including the no-picture option.
- Refine the no-address account empty state into a centered vertical card and send the CTA directly to the add-address form.

Files changed:

- `ab_ecommerce_storefront/__manifest__.py`
- `ab_ecommerce_storefront/controllers/auth.py`
- `ab_ecommerce_storefront/controllers/portal.py`
- `ab_ecommerce_storefront/models/website.py`
- `ab_ecommerce_storefront/models/res_partner.py`
- `ab_ecommerce_storefront/static/src/js/auth.js`
- `ab_ecommerce_storefront/static/src/js/avatar_picker.js`
- `ab_ecommerce_storefront/static/src/scss/auth_fields.scss`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/views/auth.xml`
- `ab_ecommerce_storefront/views/layout.xml`
- `ab_ecommerce_storefront/views/portal.xml`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/changelog.d/current.md`
