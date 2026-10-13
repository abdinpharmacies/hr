# Source Classification

Not injected into profile instructions. Original source remains `/opt/odoo19/custom-addons-ecommerce/AGENTS.md`.

Source SHA-256: `2f630668146d94cdeab3b4c9ebb415b9ff01075de551142bf442dfc620d6d66a`. Imported 2026-09-24.

Every source line is covered below. Section headings inside a range inherit its classification. Mixed introductory rules are split between concise core and module workflow.
The machine-readable [content coverage](content-coverage.json) records exact
ranges and destinations. Coverage means each section has a reviewed disposition,
not that every paraphrase is a byte-for-byte copy. Historical excerpts and all
SQL blocks have additional exact-content checks. No content-bearing section is
left only in the original file.

| Source lines | Classification | Destination / handling |
| --- | --- | --- |
| 1-41 | CORE INSTRUCTION | instructions/odoo-core.md; skills/odoo-module-development |
| 42-62 | SKILL | shared/skills/trello-workflow/SKILL.md (general, directly discoverable) |
| 63-142 | CORE INSTRUCTION | instructions/odoo-core.md |
| 143-433 | SKILL REFERENCE | skills/bconnect-eplus/references/{schema,query-patterns,synchronization,migration}.md |
| 434-466 | CORE INSTRUCTION | instructions/odoo-core.md; security review workflow |
| 467-496 | SKILL REFERENCE | skills/odoo-testing-validation/references/backups.md |
| 497-513 | SKILL | skills/odoo-testing-validation |
| 514-529 | SKILL REFERENCE | skills/odoo-module-development/references/change-records.md |
| 530-590 | SKILL | skills/odoo-translation; invariant retained in core |
| 591-648 | SKILL | skills/odoo19-compatibility; corrections in references/compatibility.md |
| 649-711 | SKILL REFERENCE | skills/odoo-module-development/references/ownership.md; security review inherited-admin check |
| 712-834 | SKILL REFERENCE | skills/odoo-module-development/references/module-conventions.md |
| 835-962 | SKILL REFERENCE | skills/odoo-security-review/references/permissions.md |
| 963-975 | SKILL REFERENCE | skills/odoo-module-development/references/module-conventions.md |
| 976-980 | SKILL | skills/odoo19-compatibility/references/compatibility.md (external API scope corrected) |
| 981-1027 | SKILL | skills/odoo-testing-validation; commands verified locally |
| 1028-1045 | CORE INSTRUCTION | instructions/odoo-core.md |
| 1046-1159 | HISTORICAL/SESSION NOTE | skills/odoo19-compatibility/references/repository-history.md; not current defect claims |
| 1160-1164 | SKILL REFERENCE | skills/odoo19-compatibility/references/compatibility.md (verified/corrected) |
| 1165-1178 | SKILL REFERENCE | skills/ab-product-seo-workflow/references/architecture.md |
| 1179-1280 | SKILL REFERENCE | skills/ab-product-seo-workflow/references/phase-0.md (historical) |
| 1281-1436 | SKILL REFERENCE | skills/ab-product-seo-workflow/references/architecture.md |
| 1437-1467 | SKILL REFERENCE | skills/ready-api-enrichment/references/api-and-pilot.md |
| 1468-1484 | SKILL REFERENCE | skills/ab-product-seo-workflow/references/architecture.md (future proposal) |
| 1485-1505 | HISTORICAL/SESSION NOTE | skills/ab-product-seo-workflow/references/architecture-request.md; conditional planning brief, not an implementation blocker |
| 1506-1595 | HISTORICAL/SESSION NOTE | skills/odoo-module-development/references/{self-inventory-history,core-ui-history}.md; conflict delimiters recorded below |

## Complete Section Index

| Line | Source heading | Classification |
| --- | --- | --- |
| 1 | AGENTS.md - Odoo 19.0 Custom Addons Development Guide | CORE INSTRUCTION |
| 42 | Trello Workflow Rules | SKILL |
| 63 | Pharmacy ERP Data Protection Rules | CORE INSTRUCTION |
| 65 | Rule #1 | CORE INSTRUCTION |
| 71 | Critical Business Data | CORE INSTRUCTION |
| 96 | Inventory Protection Rules | CORE INSTRUCTION |
| 123 | External Database Integration Rules | CORE INSTRUCTION |
| 143 | B-Connect / E-Plus Schema Reference | SKILL REFERENCE |
| 412 | Replication Safety Rules | SKILL REFERENCE |
| 434 | Product Master Protection | CORE INSTRUCTION |
| 444 | Branch Security Rules | CORE INSTRUCTION |
| 456 | Pricing Protection | CORE INSTRUCTION |
| 467 | PostgreSQL Backup Rules | SKILL REFERENCE |
| 497 | Odoo Upgrade Rules | SKILL |
| 514 | Git Rules For Hotfix Transfers | SKILL REFERENCE |
| 530 | Translation Rules | SKILL |
| 591 | Odoo 19 Compatibility Notes | SKILL |
| 593 | Views | SKILL |
| 607 | JavaScript and Assets | SKILL |
| 621 | Constraints | SKILL |
| 634 | Domains | SKILL |
| 649 | Development Rules | SKILL REFERENCE |
| 712 | Repository and Environment | SKILL REFERENCE |
| 795 | XML Rules | SKILL REFERENCE |
| 803 | Security | SKILL REFERENCE |
| 835 | Project Permission Architecture Reference | SKILL REFERENCE |
| 855 | Group Design | SKILL REFERENCE |
| 870 | ACL Semantics | SKILL REFERENCE |
| 883 | Record Rule Semantics | SKILL REFERENCE |
| 913 | Field Security | SKILL REFERENCE |
| 925 | Python Authorization and `sudo()` | SKILL REFERENCE |
| 941 | Permission Review Checklist | SKILL REFERENCE |
| 963 | Manifest Load Order | SKILL REFERENCE |
| 976 | External APIs | SKILL |
| 981 | Testing | SKILL |
| 998 | Test Port Isolation | SKILL |
| 1028 | Upgrade Safety | CORE INSTRUCTION |
| 1037 | AI Agent Rules | CORE INSTRUCTION |
| 1046 | Repository Snapshot | HISTORICAL/SESSION NOTE |
| 1048 | Modules Needing Attention | HISTORICAL/SESSION NOTE |
| 1064 | Additional Reference Modules | HISTORICAL/SESSION NOTE |
| 1083 | Odoo 19 Compatibility Issues | HISTORICAL/SESSION NOTE |
| 1085 | Critical: `_sql_constraints` | HISTORICAL/SESSION NOTE |
| 1109 | High: Legacy JavaScript (`odoo.define`) | HISTORICAL/SESSION NOTE |
| 1135 | Medium: Direct Cursor Access (`self._cr`) | HISTORICAL/SESSION NOTE |
| 1148 | Low: Manifest Version Format | HISTORICAL/SESSION NOTE |
| 1152 | Session Notes | HISTORICAL/SESSION NOTE |
| 1160 | Critical Odoo 19 Learnings | SKILL REFERENCE |
| 1165 | Phase 0 Findings — `ab_product_seo` | SKILL REFERENCE |
| 1169 | Strategic Conclusion | SKILL REFERENCE |
| 1179 | Odoo Product and Website Metrics | SKILL REFERENCE |
| 1196 | `ab_product` Metrics | SKILL REFERENCE |
| 1212 | Installed Languages | SKILL REFERENCE |
| 1221 | E-Plus `Item_Catalog` Findings | SKILL REFERENCE |
| 1269 | Useful E-Plus Lookup Tables | SKILL REFERENCE |
| 1281 | Existing Ecommerce Boundary | SKILL REFERENCE |
| 1304 | Native Odoo SEO Fields | SKILL REFERENCE |
| 1327 | `ab_product_seo` Ownership Rules | SKILL REFERENCE |
| 1354 | Required Workflow | SKILL REFERENCE |
| 1370 | Recommended Roadmap | SKILL REFERENCE |
| 1437 | Ready API Rules | SKILL REFERENCE |
| 1457 | Matching Priority | SKILL REFERENCE |
| 1468 | Future RAG Direction | SKILL REFERENCE |
| 1485 | Architecture-Only Prompt Guardrail | HISTORICAL/SESSION NOTE |
| 1506 | Session Summary — ab_self_inventory SaaS UI Redesign | HISTORICAL/SESSION NOTE |
| 1508 | Completed | HISTORICAL/SESSION NOTE |
| 1522 | Key Files | HISTORICAL/SESSION NOTE |
| 1539 | Key Decisions | HISTORICAL/SESSION NOTE |
| 1552 | Session Summary — ab_core_ui | HISTORICAL/SESSION NOTE |
| 1554 | Goal | HISTORICAL/SESSION NOTE |
| 1557 | Done | HISTORICAL/SESSION NOTE |
| 1578 | Key Decisions | HISTORICAL/SESSION NOTE |
| 1588 | Next Steps | HISTORICAL/SESSION NOTE |

## Other Sources and Adaptations

- Existing Codex Odoo profile and OpenCode Python/Odoo guidelines: SKILL, folded
  into module-development. PEP 8, typing, venv/pinned dependencies, simple design
  and ORM preferences survive. Latest-version advice becomes verified compatible
  versions, not forced dependency upgrades.
- Shared/OpenCode comment guidance: SKILL, concise module-development preference;
  preserve meaningful comments and allow essential rationale/tool annotations.
- OpenCode alwaysApply/frontmatter/skill permission globs: REPOSITORY REFERENCE,
  translated into native developer_instructions and exact managed skill entries.
- ab_template and ab_website_sale_product code: REPOSITORY REFERENCE, inspect in
  the working checkout; never copy whole addons into this profile.
- Four former review roles: CORE INSTRUCTION with conditional applicability,
  converted at the user's request into `odoo-review-rules.md`. Security,
  architecture, B-Connect and validation checks run in the main session.
  All Odoo custom subagent declarations/files are retired.
- Source merge markers at lines 1549/1550/1595: HISTORICAL/SESSION NOTE. The
  delimiter text is recorded in content-coverage.json as provenance, not active
  Markdown conflict markers. Both branches' content is preserved in the two
  module-specific historical references.

## Decisions Requiring Context

The compatibility matrix documents corrections to JS-loader, Owl-operator,
SQL-wrapper, Settings-block, SCSS and API-deprecation claims. Optional dependency
checks do not replace server-side read security. Manifest dependency order takes
precedence over the example file list. Keep development tests while excluding
them from production artifacts. Interpret developer metadata as the manifest
dictionary example, not the malformed assignment notation in the introduction.

No giant AGENTS.md copy exists here. The original repository AGENTS.md remains
unchanged and Codex still discovers it in that repository; therefore the profile
alone cannot remove that repository's existing context footprint or conflicts.
Historical snapshots are also preserved in focused, on-demand references, not as
fresh audit findings or universal development rules. A future source change must
be reclassified; the coverage check intentionally rejects a changed source hash.
