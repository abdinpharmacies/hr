
## 1fdae12fd0f4f92618ef7034380c78708693cebb

Author: emadco88
Date: 2026-10-28T20:44:54+03:00
Subject: ab_sales/ FIX customer archive error

- Recent module baseline reviewed before source-identity work.

Files changed:
- ab_sales/changelog.d/2026-10-28-converted-spare-customer.md
- ab_sales/models/ab_sales_pos_backend.py

## Current changes before commit:

- Resolve promotion eligibility through a private replica hook.
- Runtime integration verification uses isolated databases; production deployment remains separate.

Files changed:
- ab_sales/models/ab_sales_header.py

Verification: isolated receiver upgrades and clean sender installation passed; focused source authorization, promotion replica eligibility, copied metadata, sender identity, and Arabic receiver view checks passed with external network blocked. Translation format and Python syntax checks passed. No production deployment or rejected-bill replay performed.
