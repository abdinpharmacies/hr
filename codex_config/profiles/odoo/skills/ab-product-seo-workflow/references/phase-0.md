# Historical Phase 0 Measurements

Source: AGENTS.md, undated SEO discovery snapshot, imported 2026-09-24. These counts and installed-language observations are historical, not current invariants. Re-measure only the bounded facts needed for a decision. No broad production scan is authorized by this reference. Product code/eplus_serial coverage was stronger than barcode coverage; plain names were empty and required decryption. These observations inform, but do not prove, present mappings.

### Odoo Product and Website Metrics

| Metric | Count |
|--------|------:|
| `product.template` total | 110 |
| Linked to `ab_product` | 25 |
| Published website products | 106 |
| Active + saleable templates | 107 |
| Meta title filled | 0 |
| Meta description filled | 0 |
| Ecommerce description filled | 24 |
| Website description filled | 24 |
| Product images in Odoo | 1 |
| SEO optimized products | 0 |

SEO coverage is effectively zero for native meta fields. Image coverage is also a major issue and should be handled before heavy AI investment.

### `ab_product` Metrics

| Metric | Count |
|--------|------:|
| `ab_product` total | 102,834 |
| Active + saleable | 30,420 |
| With product code | 102,834 |
| With `eplus_serial` | 102,833 |
| Barcode rows | 10,000 |
| Products linked to barcode | 4,025 |
| With effective material | 7,485 |
| With description | 38,280 |
| With scientific group | 1 |

Identifier matching is strong by product code and `eplus_serial`; barcode coverage is useful but not enough as the primary key.

### Installed Languages

Installed languages:

- `ar_001`
- `en_US`

Arabic and English must be supported from day one.

### E-Plus `Item_Catalog` Findings

`Item_Catalog` contains 103,846 rows and 77 columns.

Useful fields discovered:

- `itm_code`
- `itm_name_ar_encrypt`
- `itm_name_en_encrypt`
- `com_id`
- `itm_com_code`
- `itm_ismedicine`
- `itm_scientific_n1`
- `itm_scientific_n2`
- `itm_scientific_group_id`
- `itm_usage_manner_id`
- `itm_effictive`
- `itm_effictive_perc`
- `itm_g1`
- `itm_g2`
- `itm_g3`
- `itm_origin`
- `itm_notes`
- `itm_image`

Coverage highlights:

| E-Plus Field | Count |
|--------------|------:|
| Product code | 103,846 |
| Plain Arabic name | 0 |
| Plain English name | 0 |
| Encrypted Arabic name | 103,846 |
| Encrypted English name | 103,843 |
| Manufacturer/company id | 103,794 |
| Group 1 | 73,918 |
| Group 2 | 73,697 |
| Group 3 | 68,976 |
| Scientific name 1 | 89,848 |
| Scientific group id | 65,370 |
| Usage manner id | 58,251 |
| Effective material | 7,509 |
| Notes | 38,280 |
| Origin | 103,846 |
| Image | 0 |

Important: plain Arabic and English name columns are empty. Product names appear to be stored in encrypted columns. Do not assume plain name columns are usable without confirming decryption logic.

### Useful E-Plus Lookup Tables

The following lookup tables exist and should be considered internal SEO data sources before using external APIs:

- `Company`
- `Groups`
- `Scientific_Groups`
- `item_usage_manner`
- `Usage_Causes`
- `Item_Usage_Causes`
- `Item_Origins`

