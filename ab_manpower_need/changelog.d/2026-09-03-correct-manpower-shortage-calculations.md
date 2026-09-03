# Manpower shortage variance correction

## Recent relevant commits

### c1127fd411e2240a375ab3d72f8e7d6b64c79954

Author: hager yasser <hageryasser2002@gmail.com>
Date: 2026-07-29
Subject: ab_manpower_need/FIX: solve error in translation

User-facing changes:
- Fixed Arabic translation behavior for manpower need labels and statuses.

Files changed:
- ab_manpower_need/i18n/ar.po
- ab_manpower_need/i18n/ar_001.po
- ab_manpower_need/models/manpower_hour_need.py

### 3b415d759c941561a51be0b16d20c684af63d4b0

Author: hager yasser <hageryasser2002@gmail.com>
Date: 2026-07-28
Subject: ab_manpower_need/FIX: isolate security from ab_hr and clean module structure

User-facing changes:
- Kept manpower need security and views within the module structure.
- Preserved access to job category and manpower need screens through module-owned security.

Files changed:
- ab_manpower_need/__manifest__.py
- ab_manpower_need/i18n/ar.po
- ab_manpower_need/i18n/ar_001.po
- ab_manpower_need/i18n_extra/ar.po
- ab_manpower_need/i18n_extra/ar_001.po
- ab_manpower_need/job_category_security.xml
- ab_manpower_need/models/manpower_hour_need.py
- ab_manpower_need/security/ir.model.access.csv
- ab_manpower_need/security/security_groups.xml
- ab_manpower_need/views/job_category_views.xml
- ab_manpower_need/views/manpower_hour_need_views.xml

## Current changes before commit

User-facing changes:
- Changed employee variance to current employees minus required employees.
- Changed hours variance to actual hours minus required hours.
- Classified negative variance as shortage, positive variance as increase, and zero as balanced.
- Preserved the calculated sign in employee and hour display values.
- Updated list, kanban, and search indicators so shortage means a negative variance.
- Extended tests for variance, status, display formatting, onchange behavior, view indicators, search filtering, and auto-fetch hooks.

Files changed:
- ab_manpower_need/changelog.d/2026-09-03-correct-manpower-shortage-calculations.md
- ab_manpower_need/models/manpower_hour_need.py
- ab_manpower_need/tests/test_manpower_hour_need.py
- ab_manpower_need/views/manpower_hour_need_views.xml
