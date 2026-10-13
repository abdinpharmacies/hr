# Original SEO Architecture Brief

Use this checklist for an explicitly requested architecture deliverable, alongside
[architecture and ownership](architecture.md). The old request below is preserved
for provenance, not a perpetual ban on user-authorized implementation. Phase 0
metrics are historical observations; distinguish them from reverified facts.
Return the requested architecture without code/file/commit changes when the user
asks for architecture only. Do not modify source product data or call external
services merely to produce that document.

Source: original AGENTS.md lines 1485-1505.

<!-- source-excerpt:1485-1505 -->
### Architecture-Only Prompt Guardrail

Before implementing `ab_product_seo`, ask for an architecture document only. The prompt must include:

- Do not write code.
- Do not modify files.
- Do not create commits.
- Return architecture only.
- Use Phase 0 metrics as facts.
- Follow AGENTS.md exactly.
- Design governance-first architecture.
- Use native Odoo SEO field publishing.
- Support Arabic + English.
- Include queue-based generation.
- Include versioning and rollback.
- Include audit trail.
- Keep Ready API optional.
- Include future pgvector/RAG compatibility.
- Stay compatible with `ab_website_sale_product`.
- Do not directly modify source product data.
<!-- end-source-excerpt -->
