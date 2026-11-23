# Signed-in storefront offer access

## f89fbaf81f159393444c89b0e5c9757c3c5025a4

Author: Mohamed Fawzy
Date: 2026-11-17
Original commit subject: ab_ecommerce_storefront/IMP: let shoppers choose gift quantities

- Let shoppers select quantities for eligible gift offers.

## Current changes before commit:

- Read the configured website public partner through a narrowly scoped elevated website lookup.
- Restore signed-in offer access while preserving offer eligibility and pricing calculations.

Files changed:
- models/storefront_offer.py
- changelog.d/2026-11-18-signed-in-offer-access.md
