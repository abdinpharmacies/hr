# Recent Changes

## 477718e - Mohamed Fawzy - 2026-08-03 - ab_supplier_claim_cycle/fix: 3 move security logic out of res groups

- Moved supplier claim Telegram manager logic away from direct group mutation paths.

Files changed:
- `controllers/telegram_managers.py`
- `models/ab_supplier_claim_manager.py`
- `models/ab_supplier_claim_telegram_registration.py`

## Current changes before commit:

- Added an `Employees` Telegram Management tab.
- Added automatic registration sync for employees linked to supplier claim workflow department groups.
- Added `Employee at` department assignment while keeping Telegram connection details sourced from `ab_hr_bot`.
- Added Telegram notifications for newly registered supplier claims.
- Added Telegram notifications when a supplier claim reaches a department's turn.
- Localized Telegram notifications per recipient account language.
- Used the Secretarial account language as the fallback for Telegram recipients without a user language.
- Fixed manager registrations so `Employee at` is locked to the same department as `Manager at`.
- Added a clear manager-role button beside `Manager at`.
- Added Arabic translations for the new Telegram employee screen strings.

Files changed:
- `i18n/ar.po`
- `i18n/ar_001.po`
- `models/ab_supplier_claim_cycle.py`
- `models/ab_supplier_claim_telegram_registration.py`
- `views/ab_supplier_claim_telegram_registration_views.xml`
