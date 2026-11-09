# 19.0.1.11.1 — Header search and bilingual Chatter review

Current changes before commit:

- Swap the centered search icon with the channel controls. Channels stay centered; search sits at the outer edge.
- Open the search input toward the left in LTR, mirrored in RTL, as an overlay without resizing the header or timeline. Enter submits; the native input × clears query/results. Remove separate Search, Clear and Close buttons.
- Keep pagination, context navigation, draft preservation and stale-response protection. Hide covered contact/channel content while search is open in narrow headers, without moving the layout.
- Let saved-reply content, parameters and composer text follow their own language direction. Keep Arabic interface controls mirrored while English punctuation and phone prefixes remain correctly ordered.
- Review English, ar and ar_001 Chatter at desktop, tablet and phone viewport sizes. See VALIDATION.md for executed checks and evidence.

Files changed:
- __manifest__.py
- static/src/workspace.xml
- static/src/workspace.js
- static/src/workspace.scss
- static/src/templates.xml
- VALIDATION.md
- changelog.d/2026-11-08-header-search-rtl-review.md
