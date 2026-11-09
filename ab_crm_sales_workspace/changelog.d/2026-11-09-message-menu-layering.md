# Message action menu above the composer

Changes included in implementation commit `9dc09536`:
- Remove the timeline's isolated stacking context so the last message's Reply, React and Copy menu can render above the composer.
- Keep existing menu positioning, viewport bounds, keyboard handling and composer overlay layers.
- No UI strings, translations, permissions or database records change in this fix.

Validation:
- Compiled the module SCSS with the runtime's libsass.
- Browser fixture uses the actual MessageActions component, XML templates and compiled module stylesheet with synthetic messages.
- Reproduced covered React/Copy buttons with the original isolation rule at 420px and 800px in LTR and RTL. All three menu actions pass browser hit testing with the fix in all four cases, including viewport bounds and Escape focus restoration.
- Verified keyboard and chevron opening, expanded reactions, outside dismissal, and attachment/emoji overlay hit testing in both directions.
- Authenticated live CRM validation was unavailable; no database upgrade or user-managed service restart was performed.

Files changed:
- `static/src/workspace.scss`
- `changelog.d/2026-11-09-message-menu-layering.md`
