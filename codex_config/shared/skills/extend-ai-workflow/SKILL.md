---
name: extend-ai-workflow
description: Add or change components in the ai_workflow repository and integrate them across Codex, OpenCode, installation, documentation, and validation. Use for profiles, skills, instructions, agents, plugins, MCP servers, launchers, or other workflow-owned components.
---

# Extend AI Workflow

Work from `/home/abdin_02/ai_workflow`. Read
[the component integration map](references/component-integration.md) before
editing. Inspect applicable repository instructions, analogous components, the
current working-tree diff, and generated-file ownership first.

## Required Workflow

1. Infer the component's technology and scope from its frontmatter, trigger
   description, framework names, imports, file tree, commands, and intended
   actions. Map it only to the profiles that can use it. Multi-profile does not
   mean shared: reserve shared scope for technology-independent components that
   belong in plain Codex and plain OpenCode too. Reuse one portable source when
   discovery and isolation rules allow it; do not duplicate by default. State
   the inferred technology and profile mapping before editing. If the evidence
   is ambiguous or conflicting and the choice would change enablement,
   permissions, or source ownership, ask the user one concise scope question
   instead of defaulting to shared.
2. Identify source files, generated artifacts, runtime links, permissions, and
   tests before editing. Preserve unrelated and uncommitted user changes.
3. Implement the smallest complete source change. Keep names stable and use the
   repository's existing naming, manifest, policy, and launcher conventions.
4. Update `/home/abdin_02/ai_workflow/README.md` in the same change. Document
   user-visible behavior, source and runtime locations, commands, permissions,
   compatibility boundaries, and inventory counts affected by the component.
5. Update `/home/abdin_02/ai_workflow/setup.py` in the same change. Reflect the
   component in installation, discovery, validation, preview output, permissions,
   launchers, or lifecycle behavior. When existing generic discovery already
   handles it, extend functional preview, inventory, or validation evidence so
   the component remains observable. Never add a cosmetic no-op merely to touch
   the file.
6. Register the component for each intended tool and profile. A source folder
   alone is not proof of availability. Check Codex enablement and discovery links
   as well as OpenCode discovery paths and effective skill permissions.
7. Regenerate only installer-owned artifacts through the project generator.
   Preview the exact write and link set first. Do not hand-edit generated profile
   TOML unless the generator is blocked and the user explicitly accepts a bounded
   fallback; preserve the source change that makes the next generation stable.
8. Run focused validation plus the relevant setup regression tests. Verify the
   component through a no-model discovery/config command when available.

An implementation request does not automatically authorize installing packages,
upgrading CLIs, replacing conflicting paths, or changing credentials. Preview
setup first. Apply runtime configuration only when the request includes adding or
activating the component and the plan contains no unrelated changes.

Report the component's source of truth, Codex/OpenCode scope, README and setup
changes, generated files, runtime registration, tests, and anything intentionally
left unapplied.

## Technology-to-profile routing

- Flutter and cross-platform mobile UI components belong to Flutter.
- Jaspr-specific web components belong to Jaspr. Portable Dart UI components can
  use one Flutter or Jaspr source and explicit inclusions for the other profile.
- React, browser UI, and frontend TypeScript components belong to React.
- Node backend, API, and service components belong to Node; do not enable UI-only
  components there merely because they contain JavaScript or TypeScript.
- Odoo business, ORM, deployment, and web-client components belong to Odoo.
- WordPress components belong to the OpenCode WordPress profile unless a Codex
  WordPress profile exists in the repository.
- A component spanning several of these technologies stays profile-scoped. Pick
  the most natural canonical source and register explicit inclusions and
  permissions for every other matching profile.
- Use shared scope only when the capability is useful without choosing a project
  technology, such as Git workflow, writing, repository-wide diagrams, or
  workflow maintenance.
