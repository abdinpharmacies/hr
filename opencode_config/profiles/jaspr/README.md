# Jaspr profile

Launch with `opencode-jaspr` after loading the repository shell launchers. Start a fresh
session after changes. `opencode.jsonc` loads Jaspr rules and allows nine Jaspr skills,
nine selected Dart skills, three state skills, and the existing general skills.
Flutter-only UI skills, React, Node, Odoo, and Kaisel remain denied.

Jaspr skill sources and the added Flutter library skills are mirrored in the two tool
configurations. Keep matching copies in sync when editing. Codex reuses selected skills
through `include_skills`; OpenCode uses `skills.paths` plus explicit permissions.
See [source decisions](../../../codex_config/profiles/jaspr/source-map.md).
