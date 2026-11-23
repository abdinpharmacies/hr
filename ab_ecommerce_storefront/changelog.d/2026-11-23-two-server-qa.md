# Reservation test price integrity

## f89fbaf81f159393444c89b0e5c9757c3c5025a4

Author: Mohamed Fawzy
Date: 2026-11-17
Original commit subject: ab_ecommerce_storefront/IMP: let shoppers choose gift quantities

- Let shoppers select quantities for eligible gift offers.

## Current changes before commit:

- Give the synthetic external-stock product the same price as its linked website product so reservation regressions satisfy the existing price-integrity guard.

Files changed:
- tests/test_checkout_reservation.py
- changelog.d/2026-11-23-two-server-qa.md
