# ab_sales Changelog

This file tracks the latest changes in `ab_sales` from the current branch history.

### 2026-04-18

- `8a8fafe4` - Fixed the POS unavailable-reason prompt so it appears only when the sold quantity exceeds available stock
  after UoM conversion, matching the server-side validation and adding regression coverage.

### 2026-04-16

- `df0ccfec` - Expanded receipt printing to include contract details, insurance fields, and company/customer payment
  shares, while also hardening HTML print rendering with a proper base URL wrapper.

### 2026-04-12

- `2d826dd4` - Backfilled missing Arabic translations for `ab_sales`, mainly covering labels and UI strings across the
  module.
