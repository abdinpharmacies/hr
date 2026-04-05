# AGENTS.md — Odoo 19.0 Development & Migration Guide

(Python + XML)

This file is the single source of truth for:

- Migrating code from Odoo 17.0 → 19.0
- Developing new features on Odoo 19.0
- Governing AI agents (Codex CLI, Aider, local LLMs)

Scope:

- Backend: Python ORM
- UI & configuration: XML

---

PART I — Odoo 17.0 → 19.0 Migration Notes
======================================

1) Views (XML)

--------------

List views:

- Odoo 17: <tree>
- Odoo 19: <list>

Rules:

- Always use <list> in 19.0
- view_mode must use list, not tree

Kanban views:

- Root element remains <kanban>
- Template:
    - 17.0: <t t-name="kanban-box">
    - 19.0: <t t-name="card">

attrs / states deprecation:

- attrs and states are rejected in 19.0
- Use Python boolean expressions instead

Example:
17.0:
<field name="field_b" attrs="{'invisible': [('field_a', '=', 4)]}"/>

19.0:
<field name="field_b" invisible="field_a == 4"/>

2) JavaScript & Assets

---------------------

- Legacy odoo.define(...) is deprecated
- Use ES modules:

/** @odoo-module **/
import { ... } from "@web/..."

Assets:

- Register assets in __manifest__.py
- Do not add new assets.xml files

3) ORM & SQL Constraints

-----------------------

17.0:
_sql_constraints = [
('uniq_name', 'unique(name)', 'Name must be unique.'),
]

19.0:
_uniq_name = models.Constraint(
'UNIQUE(name)',
'Name must be unique.',
)

4) Domains

----------

17.0:
from odoo.osv import expression

19.0:
from odoo import fields
domain = fields.Domain('name','=','abc') | fields.Domain('phone','ilike','7620')
domain1 = [('phone','ilike','010%')]
domain2 = [('name','ilike','any name')]
domains = fields.Domain.OR(domain1, domain2) -> return Domain object not list
for xmlrpc -> it is prefered to convert it to list

Deprecations:

- Uppercase domain operators
- <> and == operators
- Raw SQL(...) in domains
- group_operator → use aggregator

---

PART II — Odoo 19.0 Development Rules (AGENTS)
=============================================

5) Development Strategy

-----------------------

Implement features in this order:

1. Python models and logic
2. Security (ACLs + record rules)
3. XML views, actions, menus
4. Data (sequences, defaults)
5. Tests

6) Repository & Environment

---------------------------

Addon structure:
addon_name/

- __manifest__.py
- models/
- views/
- security/
- data/
- wizard/
- report/
- tests/

Python:

- Python ≥ 3.10 required
- Use virtual environments

Naming:

- Addon/module technical names must use underscores `_`
- Do not use dots `.` in addon/module names
- Example: `ab_request_management`, not `ab.request.management`

7) Python / ORM Rules

---------------------

- Always use recordsets
- Avoid per-record queries
- Use mapped / filtered / sorted

Method overrides:

- Must support multi-recordsets
- Must call super()
- No side effects in loops

Forbidden APIs:

- odoo.osv
- record._cr
- record._uid
- record._context

Required:

- record.env.cr
- record.env.uid
- record.env.context

8) XML Rules

------------

- All UI defined in XML
- Always use view inheritance
- Avoid positional XPath
- Use stable anchors

9) Security (Mandatory)

-----------------------

Every model must have:

- ir.model.access.csv
- Record rules if applicable
- Correct group usage

10) Manifest Load Order

-----------------------

- security/ir.model.access.csv
- security/*.xml
- data/*.xml
- views/*.xml
- wizard/*.xml
- report/*.xml

11) External APIs

-----------------

- Legacy XML-RPC / JSON-RPC is deprecated
- Do not build new features using them

12) Testing

-----------

Minimum:

- One business rule test
- One access/record rule test (if applicable)

13) Upgrade Safety

------------------

Code must:

- Survive 19.x upgrades
- Avoid monkey-patching
- Avoid full JS overrides
- Use XML IDs only

14) AI Agent Rules

------------------

Agents must:

- Not refactor unrelated files
- Not rename XML IDs unless instructed
- Make smallest valid diff
- Reject deprecated APIs

---

15) New res.groups.privilege Layer

----------------------------------
<!-- 1. Category -->
<record id="module_category_hospital" model="ir.module.category">
    <field name="name">Hospital</field>
    <field name="sequence">20</field>
</record>

<!-- 2. Privileges (The "Logic" Layer) -->
<record id="privilege_hosp_medical" model="res.groups.privilege">
    <field name="name">Medical Access</field>
    <field name="category_id" ref="module_category_hospital"/>
</record>

<record id="privilege_hosp_admin" model="res.groups.privilege">
    <field name="name">Full Admin</field>
    <field name="category_id" ref="module_category_hospital"/>
    <field name="implied_ids" eval="[(4, ref('privilege_hosp_medical'))]"/>
</record>

<!-- 3. Groups (The "User" Layer) -->
<record id="group_hosp_nurse" model="res.groups">
    <field name="name">Nurses</field>
    <field name="privilege_id" ref="privilege_hosp_medical"/>
</record>

<record id="group_hosp_surgeon" model="res.groups">
    <field name="name">Surgeons</field>
    <field name="privilege_id" ref="privilege_hosp_admin"/>
</record>

----
END OF AGENTS.md
