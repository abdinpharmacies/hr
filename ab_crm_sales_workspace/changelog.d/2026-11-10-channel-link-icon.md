# Header channel-link icon

## Committed baseline

- Commit: `2702b7f16d06c516db1ae66d7d8f592432396edd`
- Author: `Alhassan Hossny`
- Date: `2026-11-09T14:05:37+02:00`
- Original subject: `ab_crm_sales_workspace/docs: record grouped chatter and menu fixes`

## Changes included in implementation commit `77209fcb`

- Version 19.0.1.21.0 moves the existing contact-link action beside the channel icons as an accessible chain-link button. The existing picker associates the current conversation with a saved customer and refreshes the grouped channel icons.
- Keep customer-only headings and no header notification badges. Preserve server-side ownership checks, destination histories and existing linking rules.
- Use the existing translated label in English and both Arabic catalogs. Keep the icon aligned with search and hide it behind the narrow search overlay.

Files changed for this increment:
- `__manifest__.py`
- `static/src/workspace.xml`
- `static/src/workspace.scss`
- `changelog.d/2026-11-10-channel-link-icon.md`
