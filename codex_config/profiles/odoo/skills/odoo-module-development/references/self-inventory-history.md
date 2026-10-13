# Historical Self-Inventory UI Decisions

Read only for `ab_self_inventory` UI maintenance. This undated session record
preserves design intent, affected paths, widget behavior and test expectations;
it does not prove the current checkout contains these changes. Verify current
files before acting. Do not generalize its styling or dialog choice to all modules.
Use the [verified compatibility corrections](../../odoo19-compatibility/references/compatibility.md)
for Owl operators and CSS imports. Completed operations below are history, not
instructions to rerun them.

Source: original AGENTS.md lines 1506-1548.

<!-- source-excerpt:1506-1548 -->
## Session Summary — ab_self_inventory SaaS UI Redesign

### Completed
- **List view card rows**: White bg, rounded corners, shadow hover, left accent border (`self_inventory.scss`).
- **Premium state badges**: Gradient + glow (`.ab_state_badge`).
- **Deadline color coding**: Green/orange/red/past urgency with icon + relative text (`.ab_deadline_widget`).
- **Quick actions dropdown**: "..." button on row hover with Open/Edit/Duplicate (`.ab_quick_actions_menu`).
- **Branch popover tooltip**: Body-level DOM append, sync `getBoundingClientRect()` before await, absolute positioning with scrollX/Y.
- **Kanban views**: Created for all 3 models (batch/request/process) with KPI row, branch pill, deadline, requester meta, grouped by state (`self_inventory_kanban_views.xml`).
- **Form redesign**: Hero card, KPI cards row (4-column grid with top accent), two-column layout (1fr 340px sidebar), branch chips, progress SVG circle, state-based timeline, sidebar info cards (`self_inventory_form.scss`, `self_inventory_form_widgets.js`).
- **5 form OWL widgets**: FormHeroWidget, KpiCardWidget (with shortage/extra types), BranchFormWidget, FormProgressWidget, TimelineWidget.
- **6 list/kanban OWL widgets**: BranchPillsWidget (body-level popover), KpiWidget, StateBadgeWidget, RowTitleWidget (with quick actions), DeadlineWidget, BranchDialog.
- **Bulk product codes OWL Dialog**: Replaced old `TransientModel` wizard form with `BulkImportResultsDialog` — summary cards (branches processed / added / missing), branch table, expandable missing-codes section, "Download Missing Codes" button, empty state. Triggered via `ir.actions.client` with tag `ab_inventory_bulk_code_results`.
- **Dead code removal**: Removed `SelfInventoryBatchCodeResultWizard`, `SelfInventoryBatchCodeResultLine` transient models, their form view in batch views XML, and their 4 access lines from `ir.model.access.csv`.
- **Test updated**: `test_batch_add_product_codes` now asserts `ir.actions.client` params instead of wizard `res_model/res_id`.

### Key Files
| File | Purpose |
|---|---|
| `ab_self_inventory/static/src/scss/self_inventory.scss` | List/kanban SCSS |
| `ab_self_inventory/static/src/scss/self_inventory_form.scss` | Form SCSS + bulk dialog SCSS |
| `ab_self_inventory/static/src/js/self_inventory_widgets.js` | 6 list/kanban widgets |
| `ab_self_inventory/static/src/js/self_inventory_form_widgets.js` | 5 form widgets |
| `ab_self_inventory/static/src/js/self_inventory_bulk_code_dialog.js` | BulkImportResultsDialog + client action handler (NEW) |
| `ab_self_inventory/models/self_inventory_request.py` | `_get_bulk_code_result_action()` replaces wizard open; removed wizard models |
| `ab_self_inventory/views/self_inventory_kanban_views.xml` | Kanban views |
| `ab_self_inventory/views/self_inventory_request_batch_views.xml` | Batch list + form; removed wizard form view |
| `ab_self_inventory/views/self_inventory_request_views.xml` | Request list + form |
| `ab_self_inventory/views/self_inventory_process_views.xml` | Process list + form |
| `ab_self_inventory/security/ir.model.access.csv` | Removed 4 wizard access lines |
| `ab_self_inventory/__manifest__.py` | Asset registration (added bulk_code_dialog.js) |
| `ab_self_inventory/tests/test_self_inventory.py` | Updated assertions for client action |

### Key Decisions
- Popover DOM appended to `document.body` (not nested inside widget) to avoid ancestor CSS `transform`/`will-change` clipping.
- `getBoundingClientRect()` captured synchronously before `await` in `onEnter()` to avoid zero-rect from virtual-scrolling detach.
- Form widgets access sibling fields via `this.props.record.data.fieldName` — handle both raw values and Many2one arrays.
- ProgressWidget computes `percent = Math.round((processed / requested) * 100)` with safe division-by-zero.
- TimelineWidget generates items from record state/dates via static `timelineMap` — no separate history model required.
- **OWL template operators**: JavaScript operators (`!`, `&&`, `||`) with XML entity escaping (`&amp;` for `&`) — NOT QWeb-style `not`/`and`/`or`.
- **SCSS `@import url()` removed** from form SCSS to prevent libsass failure from breaking the entire backend asset bundle.
- **Bulk code results**: `ir.actions.client` → OWL Dialog (no TransientModel wizard, no ValidationError).
- **Dialog "Download Missing Codes"** uses client-side Blob + anchor download (no server round trip).
<!-- end-source-excerpt -->
