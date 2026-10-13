# Historical Core UI Design Decisions

Read only for `ab_core_ui` design-system/workspace maintenance. Keep its launcher,
workspace and namespace decisions scoped to that module. Verify current code;
this undated session is not evidence of installed features or completed testing.
The source's cache deletion and cron deactivation are historical actions, never
permission to repeat them. Pending steps require a current task and authorization.
Use the [verified compatibility corrections](../../odoo19-compatibility/references/compatibility.md)
for Settings block groups, Owl props/handlers and module exports. Preserve the
module's reduced-motion support when changing its transitions.

Source: original AGENTS.md lines 1551-1594.

<!-- source-excerpt:1551-1594 -->

## Session Summary — ab_core_ui

### Goal
Build a complete Design System and Component Workspace module `ab_core_ui` as the centralized Odoo 19 UI foundation. Settings page is ONLY an elegant launcher — no configuration, no statistics, no galleries. Workspace is a fullscreen immersive experience with cinematic entry/exit transitions.

### Done
- Full module scaffolding: manifest, models, views, security, data, static assets.
- 5 Python models: `core_ui.category` (hierarchical), `core_ui.component`, `core_ui.design_token`, `core_ui.pattern`, `res.config.settings`.
- Security: 3 groups (User/Developer/Manager) using Odoo 19 privilege-based hierarchy.
- 30+ reusable QWeb component templates, 24 default categories, 41 components, 30+ design tokens, 7 patterns.
- 7 OWL JS components + OWL XML templates.
- **Fixed search view**: Removed invalid `expand="1" string="Group By"` from `<group>` in Odoo 19.
- **Fixed core_ui_transition.js**: Removed `export {};` causing `export declarations may only appear at top level of a module`.
- **Deleted corrupted cached bundles** forcing regeneration.
- **Deactivated ab_product_seo cron #78** (non-existent method).
- **Fixed Settings section rendering**: Removed `groups="group_core_ui_user"` from `<block>` — XML ID resolution in inherited views stripped the block despite `has_group()` returning True.
- **Simplified res_config_settings.xml**: Entire Core UI block replaced with a single centered launcher card: icon + title + subtitle + one premium "Launch Workspace" button. Cards, statistics, settings fields, badges, and gallery button removed.
- **Fixed OWL prop validation** for 4 nullable props: `selectedCategory`, `categoryId`, `selectedComponent`, `component` — changed from `{ type: String }` / `{ type: Object }` to canonical union `[Type, { value: null }]`.
- **Fixed OWL template inline JS**: Moved `const __handler = ...; if (__handler) ...` from `t-on-click` to a component method — OWL's expression parser cannot handle statement blocks.
- **Cinematic 4-phase entry transition**: (1) Settings page blurs + scales down, (2) dark overlay fades in with backdrop-filter, (3) workspace grows from center with spring easing + border-radius transition, (4) staggered element reveal (topbar → sidebar → gallery → inspector) with translateY+opacity.
- **Reverse 4-phase exit transition**: Elements fade out in reverse stagger → workspace shrinks → overlay fades → settings page restores.
- **Premium Launch Workspace button**: Gradient bg, hover lift + scale, active press, glow shadow, focus-visible ring, ripple container, spring easing.
- **Settings launcher card**: Hover lift + border glow, centered layout, gradient icon container, premium typography.
- **Dead code removal**: Removed `.core_ui_settings_card`, `.core_ui_stat_card`, `.core_ui_badge` from SCSS. Removed duplicate `.core_ui_badge_pill` and `.core_ui_empty_state` definitions from variables.scss (already in components.scss).
- **`prefers-reduced-motion` support**: All transitions disabled when user prefers reduced motion.

### Key Decisions
- Changed module name to `ab_core_ui` but kept design system namespace `core_ui.*` for component IDs.
- Odoo 19 security: `res.groups.privilege` → `res.groups` chain.
- **Settings is only a launcher** — no config panels, statistics, or options exposed. The workspace IS the experience.
- **Cinematic transitions via CSS classes + JS timers**: No JS animation library. 4-phase entry/exit with staggered delays, spring easing, and backdrop blur.
- **Staggered element reveal uses CSS-only selectors** — not `core_ui_element_enter` classes on each element. Targets `.core_ui_sidebar`, `.core_ui_gallery`, etc. directly via `.core_ui_workspace:not(.core_ui_elements_visible)` and `.core_ui_workspace.core_ui_elements_visible`.
- Nullable OWL props use canonical `[Type, { value: null }]` union pattern (matching Odoo 19's error_dialogs.js, datetime_picker.js).
- **No `groups` attribute on `<block>` in inherited `res.config.settings` views** — causes block stripping even when `has_group()` returns True.
- **No inline JS statements in OWL `t-on-click`** — only expressions. Use component methods for logic.

### Next Steps
1. Verify the Settings launcher renders in browser (hard refresh Ctrl+Shift+R).
2. Test Launch Workspace button — cinematic entry should play.
3. Test Exit button — reverse cinematic exit should play.
4. Verify component gallery, sidebar filters, search, inspector all work.
5. Test `t-call` from another module.
6. Add keyboard shortcuts, more component templates.
<!-- end-source-excerpt -->
