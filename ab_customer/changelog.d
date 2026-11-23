Current changes before commit:

- Remove Customer inheritance of the retired cost-center second-authentication model. Preserve Customer messaging and E-Plus metadata.

Files changed:

- ab_customer/changelog.d
- ab_customer/models/ab_customer_inherit.py

commit 3db5d596c9429ff082c3fe9b0466692b945f788f
Author: emadco88 <emadco88@gmail.com>
Date:   2026-07-28T15:21:42+03:00

    INIT commit pos19

- Introduce Customer records, contacts, security, and customer screens.

Files changed:

- ab_customer/__init__.py
- ab_customer/__manifest__.py
- ab_customer/models/__init__.py
- ab_customer/models/ab_customer.py
- ab_customer/models/ab_customer_contact.py
- ab_customer/models/ab_customer_inherit.py
- ab_customer/security/ir.model.access.csv
- ab_customer/security/record_rules.xml
- ab_customer/security/security_groups.xml
- ab_customer/static/description/icon.png
- ab_customer/views/ab_customer.xml
