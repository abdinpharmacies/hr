---
name: pg-graph
description: Consult Apache AGE and openCypher references only for an explicit PostgreSQL graph or knowledge-graph task in the Odoo profile. Verify AGE availability, the target database, and pharmacy data boundaries before proposing graph schema or data changes.
---

# Apache AGE graph reference for Odoo

Use the upstream [graph routing guide](upstream-SKILL.md) and relevant [references](references/) when the user asks about Apache AGE, openCypher, a knowledge graph, or graph-based retrieval. Ordinary Odoo model relationships and SQL joins do not require this skill.

Read project instructions and verify the target is an authorized PostgreSQL database with AGE available. Keep exploration read-only and bounded. Do not copy pharmacy records, branch data, pricing, inventory, or patient/customer information into a graph without an explicit data design and authorization. External B-Connect/E-Plus remains read-only.

Before creating extensions, graphs, labels, indexes, vertices, edges, embeddings, or changing data, prepare the exact target and impact and follow the user's authorization and environment approval controls. Validate any generated Cypher against the real schema; never concatenate untrusted input. An absent `postgres-mcp` does not prevent conceptual guidance, but connected operations require an authorized interface.

This package provides a skill and references, not a subagent or an always-on rule.
