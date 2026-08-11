## Current changes before commit

User-facing changes:

- Added configurable sales channels for POS sales.
- Added the Sales Channel field to sales bills and required it before submit.
- Added the Sales Channels configuration menu for sales managers and system administrators.
- Added default sales channel records and Arabic translations.

Files changed:

- `ab_sales_channel/__init__.py`
- `ab_sales_channel/__manifest__.py`
- `ab_sales_channel/changelog.d/2026-08-11-sales-channel.md`
- `ab_sales_channel/data/ab_sales_channel_data.xml`
- `ab_sales_channel/i18n/ar.po`
- `ab_sales_channel/i18n/ar_001.po`
- `ab_sales_channel/models/__init__.py`
- `ab_sales_channel/models/ab_sales_channel.py`
- `ab_sales_channel/models/ab_sales_header.py`
- `ab_sales_channel/security/ir.model.access.csv`
- `ab_sales_channel/static/src/pos/sales_channel_patch.js`
- `ab_sales_channel/static/src/pos/sales_channel_templates.xml`
- `ab_sales_channel/views/ab_sales_channel_views.xml`
- `ab_sales_channel/views/ab_sales_header_views.xml`
