Current changes before commit:

- Retain name, code, code-list search, work email, and archive status in the core cost-center model. Preserve separate E-Plus synchronization metadata.
- Remove the second-authentication abstract model and obsolete cost-center view fields.
- Preserve existing Arabic translations and cover retained labels for both supported Arabic codes.
- Preserve cost-center archive/unarchive behavior and existing Accounting checks. Verify compatibility with the reduced HR model and Customer inheritance.

Files changed:

- ab_costcenter/changelog.d
- ab_costcenter/i18n/ar.po
- ab_costcenter/i18n/ar_001.po
- ab_costcenter/models/__init__.py
- ab_costcenter/models/ab_costcenter_second_auth.py
- ab_costcenter/models/costcenter.py
- ab_costcenter/views/costcenter.xml

commit 3db5d596c9429ff082c3fe9b0466692b945f788f
Author: emadco88 <emadco88@gmail.com>
Date:   2026-07-28T15:21:42+03:00

    INIT commit pos19

- Introduce cost-center records, E-Plus metadata, secondary authentication, and administrator screens.

Files changed:

- ab_costcenter/__init__.py
- ab_costcenter/__manifest__.py
- ab_costcenter/i18n/ar_001.po
- ab_costcenter/models/__init__.py
- ab_costcenter/models/ab_costcenter_eplus_inherit.py
- ab_costcenter/models/ab_costcenter_second_auth.py
- ab_costcenter/models/costcenter.py
- ab_costcenter/security/ir.model.access.csv
- ab_costcenter/security/security.xml
- ab_costcenter/static/description/icon.png
- ab_costcenter/static/src/js/archive_security.js
- ab_costcenter/test.txt
- ab_costcenter/views/costcenter.xml
