# Profile completion celebration

Recent relevant commit:

- Commit: `48383f8333c91ebaf9c19b54ee3f6eb67b6fe11c`
- Author: Mohamed Fawzy
- Date: 2026-09-03
- Original subject: `ab_ecommerce_storefront/fix: polish auth flow and avatar completion`
- Persisted avatar-choice completion and updated the profile percentage immediately after saving an avatar.
- Files changed (completion context): `ab_ecommerce_storefront/models/res_partner.py`, `ab_ecommerce_storefront/static/src/js/avatar_picker.js`.

Current changes before commit:

- Play the existing personal-information completion animation once per account at 100%, then dismiss the completion strip permanently across browsers and devices.
- Replace automatic CSS triggers on every 100% page load with an explicit animation class after a server acknowledgement.
- Store the acknowledgement on the authenticated user, protect the field from portal ORM access, and use an Odoo row lock to prevent concurrent requests from claiming the same celebration.
- Accept only authenticated, CSRF-protected POST requests. Derive the target from the session and recheck the completion percentage on the server.
- Omit previously acknowledged completion strips from server-rendered account pages, even if the profile becomes incomplete and is later completed again.
- Handle immediate avatar completion, viewport visibility, reduced motion, request failures, navigation and animation cleanup.
- Add the field label to both Arabic catalogs using an Odoo POT export. Preserve the existing completion copy and delivery-order celebration.
- This entry covers only profile completion; other current storefront changes are documented separately.

Files changed:

- `ab_ecommerce_storefront/__manifest__.py`
- `ab_ecommerce_storefront/models/res_users.py`
- `ab_ecommerce_storefront/controllers/portal.py`
- `ab_ecommerce_storefront/views/portal.xml`
- `ab_ecommerce_storefront/static/src/js/avatar_picker.js`
- `ab_ecommerce_storefront/static/src/js/profile_completion.js`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/changelog.d/2026-10-14-profile-completion-once.md`

Validation:

- Targeted storefront upgrades passed on `codex_ecom_offers_20261013` with ports 5069/5072, HTTP and cron disabled.
- Eleven simulated-DOM JavaScript lifecycle checks passed in `/tmp/validate_profile_completion.cjs`.
- Eleven Odoo checks passed in `/tmp/validate_profile_completion.py`: complete/incomplete eligibility, persistent acknowledgement, portal field read/write denial, other-record targeting, public-user rejection, profile regression, concurrent transaction locking, route authentication/CSRF metadata, QWeb omission and runtime Arabic field translation.
- All ORM test changes were rolled back. No customer data or acknowledgement was changed on the active database.
- Python/XML syntax, JavaScript syntax, complete storefront SCSS compilation, both `msgfmt --check-format` checks and `git diff --check` passed.
- Browser visual verification remains unavailable in this session. HTTP authentication and CSRF were checked through route configuration, not a live browser request.
- Upgrade logs include a missing attachment in the isolated database filestore and unrelated existing module warnings; both upgrades completed successfully. Full-page asset/image validation remains unverified.
- Activation requires loading the changed Python code and a targeted storefront upgrade on the running instance. Its process was not stopped or restarted.
