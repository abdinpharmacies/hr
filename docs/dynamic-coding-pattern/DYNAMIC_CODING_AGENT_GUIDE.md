# Dynamic Coding Agent Development Guide

## Purpose

Follow these instructions when creating a new Odoo module or editing an existing module to make its workflow configurable and extensible. Keep changing configuration separate from shared execution logic and business-specific validation. Apply only the abstractions needed by the requirement.

## 1. Inspect and classify before editing

1. Read applicable `AGENTS.md` files and inspect the target module, dependencies, security rules, views, and tests.
2. Trace the current workflow from user action through authorization, validation, writes, audit, and UI refresh.
3. Identify repeated conditions, duplicated action methods, fixed role assignments, field allowlists, and fixed component sequences.
4. Classify each behavior as configurable variation, shared execution, business-specific policy, presentation, or security invariant.
5. Record what must remain compatible: XML IDs, public actions, existing records, integrations, translations, and running operations.
6. Define a clear acceptance criterion for making the behavior dynamic. A new configured component should reuse the existing executor without requiring another component-specific method.

Do not convert every constant or condition into configuration. Keep a simple fixed rule in Python when there is no meaningful variation to administer.

## 2. Choose configuration or Python deliberately

| Requirement | Implementation instruction |
|---|---|
| Change labels, responsible users, ordering, or permitted existing fields | Use validated configuration records when this variation is part of the requirement. |
| Select applicable configurations using existing business fields | Use literal domains validated against the intended model. |
| Add a new business field or form layout | Extend Python/XML, then expose the field through configuration if permitted. |
| Add a new decision meaning, quorum, calculation, or integration operation | Define explicit Python behavior and a tested extension contract. |
| Protect identity, company/branch scope, prices, or inventory | Enforce backend invariants independently of administrator configuration. |
| Add arbitrary executable expressions or callable names | Do not use them as a shortcut to extensibility. Define bounded supported behavior instead. |

Identify who maintains each setting and validate that setting on the server. Do not create configuration that an administrator cannot understand or safely maintain.

## 3. Separate architecture responsibilities

| Layer | Instructions |
|---|---|
| Configuration definitions | Store applicability, lifecycle, version, reusable components, ordering, assignments, and permitted metadata. |
| Runtime state | Store each operation's selected definition, component results, current progress, decisions, actors, and timestamps. |
| Shared executor | Centralize starting, authorizing, deciding, progressing, completing, and recording outcomes. |
| Business policies | Keep required business fields, value validation, calculations, and domain-specific completion behavior in narrow methods. |
| Presentation | Render runtime rows and backend permissions through XML and module-scoped widgets. |
| Audit | Append durable action outcomes through checked internal calls. |

Do not put a branch for each configurable component into the executor. Do not duplicate the executor to change one business rule. Start with module-local policy methods; extract a shared abstract engine only when multiple consumers need the same semantics.

Avoid undeclared dependencies on external models. Follow project guidance for runtime integration boundaries or explicitly required module dependencies. Keep changes confined to the module and approved integration surface.

## 4. Design definitions and runtime state

- Separate reusable definitions from operation instances. Link each runtime component to its operation and definition component.
- Enforce required relationships, valid sequence values, unique definition/version pairs, and unique runtime component instances where appropriate.
- Give definitions a governed activation lifecycle. Validate required components, actors, fields, and matching conditions before activation.
- Define behavior for zero, one, and multiple matching configurations. A useful default is to block start when none match, select the sole match, and require an explicit choice when several match. Ordering alone must not silently resolve ambiguity.
- Parse domains as literal data and validate them against the intended model. Recheck the selected configuration when starting execution.
- Review compute/onchange dependencies whenever matching inputs change. Do not assume configuration creates reactive dependencies automatically.
- Decide which configuration values remain live and which are copied into runtime state. Document the effect of reassignment or field-permission changes on running operations.
- Version structural changes that would invalidate running operations. Define which edits are permitted after activation and how historical definitions remain available.
- Protect records through archiving when their identity or history must be preserved.

Use ordered groups only when the workflow requires them. If equal sequences mean parallel components, define whether all components must complete before advancing. Distinguish eligible actors from voting requirements: multiple assigned users do not inherently imply unanimous approval. Design conditional graphs and quorum semantics explicitly if required.

## 5. Implement one guarded execution path

For every public workflow action:

1. Check operation access and ownership of the requested runtime component in the caller's environment.
2. Lock affected records where concurrent actions can collide, refresh relevant state, and recheck access and actionability.
3. Validate the actor, supported action, current state, input values, and business invariants.
4. Apply runtime changes through a trusted internal path with narrowly justified elevation, if needed.
5. Advance the common algorithm, invoke permitted business hooks, and append audit history in the same transaction.
6. Return a result the UI can refresh. Ensure failures roll back partial progress.

Never treat a private method name, context flag, hidden button, or wizard opening as authorization. Do not let caller-supplied context bypass access or protected-field checks. Recheck permissions when a wizard confirms its action.

For external effects, design a transactional queue, stable identity keys, retries, and idempotency separately. A database transaction does not make a remote action exactly-once.

## 6. Define narrow extension points

Choose method names consistent with the target module. The following contracts are illustrative, not required framework APIs:

| Contract responsibility | Expected interface |
|---|---|
| Validate operation start | Business recordset; raises on missing or invalid business data; does not advance progress. |
| Match definitions | Persisted operation singleton; returns eligible definitions within access scope. |
| Authorize component execution | Operation and owned runtime component; returns a boolean or raises according to the declared contract. |
| Compute editable fields | Operation in current user context; returns a set of permitted field names. |
| Validate a decision | Owned component, supported decision, and input values; raises on business-policy violations. |
| Handle completion | Completed operation recordset; applies explicitly supported business behavior through the guarded completion path. |

Document recordset expectations, return values, side effects, and failure behavior. Preserve `super()` when extending existing contracts, support multi-record operations where appropriate, and use `ensure_one()` for singleton commands.

Add a configured component for a new instance of existing behavior. Extend a business-policy method for a new invariant. Change the executor only when the execution semantics actually change, and test that change separately.

## 7. Enforce metadata permissions and secure presentation

If configuration controls field editability, link to existing field metadata rather than creating duplicate field-name logic throughout the module. Validate model ownership and exclude nonstored, computed, related, technical, identity, company, and workflow-control fields as required by the business policy.

Compute permitted fields centrally from current operation state, active components, actor assignments, and privileged roles. Enforce the same policy in backend writes and expose a serialized result for XML readonly expressions. Metadata permissions select existing fields; they do not create schema or layouts.

Render component lists and available actions from runtime records. Use module-scoped widgets when necessary, with backend-computed actionability. Keep action vocabulary explicit, reload state after commands, and handle errors without leaving the UI permanently busy.

Define ACLs for every new model and record rules wherever data isolation applies. Check the highest privilege first before applying restricted roles inherited through group membership. Test combined roles, historical versus current membership, and company/branch boundaries independently. Historical visibility must not grant current decision authority.

## 8. Follow development and data-protection standards

- Implement model logic, security, XML views/actions, required runtime data, and tests in that order.
- Use project-supported Odoo APIs, including `models.Constraint`, `fields.Domain`, `<list>` views, expression-based XML modifiers, ES modules, and manifest-registered assets where applicable.
- Extend existing views with stable inherited anchors. Avoid positional XPath, monkey patches, shared frontend overrides, and deprecated APIs.
- Use recordsets and batch operations where practical. Measure repeated matching queries before introducing broad synchronization or large batches.
- Preserve critical records, stable identifiers, XML IDs, and translations. Do not delete business history or silently relink completed operations.
- Change stock through approved stock operations rather than directly assigning computed quantities. Preserve required price-change traceability and product-identity protection.
- Keep external databases read-only unless explicitly authorized otherwise.
- Follow project requirements for backups, targeted upgrades, manifests, and module scaffolding. Do not create demo data or unnecessary hooks, cron jobs, or SQL.
- Keep the diff limited to the requested change. Do not mix unrelated cleanup with architecture work.

## 9. Make an existing workflow dynamic safely

1. Map existing behavior and add meaningful regression coverage before replacing duplicated execution paths.
2. Identify which fixed behavior becomes configuration and which existing rules remain explicit Python.
3. Introduce the smallest definition/runtime separation needed. If existing records need conversion, define a deliberate migration preserving identity, audit history, and active progress.
4. Replace repeated action implementations with a common executor and policy hooks incrementally. Preserve existing public actions or provide compatibility wrappers when integrations depend on them.
5. Populate only required runtime configuration through the project's approved mechanism. Avoid broad database edits and automatic changes to running operations.
6. Verify old supported behavior and new configuration cases before removing redundant paths. Document any intentional behavior change.

Do not silently reinterpret historical records under a new definition. If coexistence is needed during migration, declare which records use each execution path and when compatibility code can be removed.

## 10. Test business behavior and security

Include at least one business-rule test and an access/record-rule test where applicable. Test relevant cases from this matrix:

| Area | Required scenarios |
|---|---|
| Definitions | Invalid domains, unusable actors, protected/foreign fields, empty definitions, invalid sequences, and duplicate runtime instances. |
| Matching | Zero/one/multiple candidates, changed inputs, dependency refresh, and stale selection at start. |
| Progression | Supported sequential/parallel behavior, supported decisions, terminal-state protection, and invalid ownership. |
| Business rules | Missing inputs, invalid values, decision-specific requirements, and completion-policy behavior. |
| Authorization | Unassigned actors, forbidden writes, direct backend calls, forged context flags, and stale wizard permissions. |
| Isolation | Required company/branch scope, inherited administrator membership, combined groups, and historical visibility versus current authority. |
| Configuration changes | Live reassignment, permission revocation, immutable snapshots where required, and structural-version compatibility. |
| Transactions and audit | Rollback on failure, correct action history, rejected audit mutation, and no partial progress. |
| Extensions | A new configured component reuses the executor; a policy extension preserves shared execution contracts. |
| Migration and concurrency | Existing records retain intended behavior; simultaneous decisions do not double-advance; concurrent version creation follows the declared policy. |
| UI and performance | Record-driven actions refresh correctly; backend checks survive UI bypass; query costs remain acceptable at expected scale. |

Run targeted checks in a disposable environment. Do not use production installation or upgrades to verify documentation, and never run a broad base upgrade for a focused change. Report executed tests separately from source inspection or proposed test coverage.

## 11. Deliver and monitor

Document configuration ownership, supported edits, extension contracts, migration requirements, rollback/recovery behavior, and limits. Verify that operators can understand invalid-configuration errors and safely restore a usable definition.

For implementation changes, review execution failures, audit completeness, and matching performance after rollout. Protect existing records and configuration during targeted upgrades.

Before finishing, verify:

- A new configured component reuses shared execution without another component-specific method.
- Business policies, security invariants, and common execution remain separate.
- Every configurable setting has validation and an owner.
- UI permissions agree with backend enforcement.
- Live-versus-snapshot behavior and migration effects are explicit.
- Extension contracts and access boundaries have meaningful tests.
- Documentation distinguishes implemented behavior from illustrative or future design.
- The final diff contains only authorized changes and reports validation accurately.
