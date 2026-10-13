---
name: ready-api-enrichment
description: Evaluate or implement optional Ready API enrichment with a controlled pilot, product matching, caching and queued rate limits.
---

Use for requested enrichment/evaluation only. Ready is optional, never the source
of truth. Prefer internal E-Plus data and native SEO governance. Read
[API notes and pilot](references/api-and-pilot.md); verify historical limits before use.

Start with a manually controlled 100-product pilot. Match by barcode, eplus_serial,
product code, scientific group, normalized name, then fuzzy similarity. Record
provenance/confidence and review ambiguous matches. Similar names alone cannot
justify overwriting product identity or medical facts.

Cache responses, rate-limit to verified account limits, use bounded queues and
manual start/stop/retry control. Never call Ready during website rendering or
automatically enrich/publish the full catalog. Do not put credentials in code,
logs, public fields or references.

Measure match rate, incremental data quality, Arabic quality and scientific
quality against internal data. Keep Ready only when it adds measured value.
Enrichment feeds reviewable drafts, never unreviewed product-master, stock,
pricing or published medical content.
