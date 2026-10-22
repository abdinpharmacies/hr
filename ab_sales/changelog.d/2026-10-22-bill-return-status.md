# Bills with confirmed returns

## Recent relevant commit

- Commit: c267769c3bc67e44c7af65f544ae665770b3cadd
- Author: Hossam Elsheikh <hossam.m.elsheikh@gmail.com>
- Date: 2026-10-21 16:00:37 +0300
- Original commit subject: ab_sales/The callcenter preview exposed a missing _price_ref_from_line helper that prevents “Buy 1 get 1 free” from calculating. I’ve fixed that blocker and reruned the previews before saving the test offers
- Restored price-reference conversion for promotion previews.
- Files changed:
  - __manifest__.py
  - models/ab_sales_header.py
  - changelog.d/2026-10-21-promotion-price-reference.md

## Current changes before commit:

- Add read-only, non-stored computed Boolean `ab_sales_header.has_returns` based on saved callcenter return records, matched by branch and original invoice number. Draft/pending returns do not count; archived saved returns still count.
- Batch return lookup through one ORM grouped query, respecting existing return access rules without sudo. No external calls during field computation.
- Invalidate cached indicators when a return is created or its status, branch or invoice changes.
- Show a module-specific Boolean badge in the Bills list, a tag on the bill form, and tags in the invoice browser list/details.
- Export and merge the new English/Arabic label and help text for ar and ar_001.
- Upgrade version to 19.0.4.1.6.

Files changed:
- __manifest__.py
- models/__init__.py
- models/bill_return_status.py
- models/ab_sales_ui_api_bill_wizard_inherit.py
- views/local_bill_views.xml
- static/src/bill_wizard/has_returns_badge.js
- static/src/bill_wizard/has_returns_badge.xml
- static/src/bill_wizard/bill_wizard_action.xml
- i18n/ar.po
- i18n/ar_001.po
- changelog.d/2026-10-22-bill-return-status.md

Verification:
- ORM checks cover no return, draft, pending, saved, archived, empty invoice identity, same invoice number in different branches, and cache invalidation after branch changes.
- Batch computation uses one grouped return query. Invoice-browser payload marks sale records only; inherited Bills list contains the scoped widget.
- Test fixtures rolled back; no branch API calls, external writes or stock changes. Scripts retained outside addons in /tmp/callcenter-ui.
- Runtime checks match confirmed returns to 40 existing bills, verify Arabic field/menu labels, and confirm the badge template is included in installed assets.
- Targeted ab_sales upgrade passed. Both PO files pass msgfmt --check-format; JS syntax and git diff --check pass.

Scope: the indicator covers confirmed returns recorded in the callcenter. Returns created exclusively in a branch and never synchronized into the callcenter are not inferred by this local field.
