# Component Integration Map

Use the current repository as the source of truth. This map identifies the usual
ownership and checks; it does not replace inspecting an analogous component.

## Shared or profile skill

| Concern | Shared | Profile-specific |
| --- | --- | --- |
| Codex source | `codex_config/shared/skills/<name>/` | `codex_config/profiles/<profile>/skills/<name>/` |
| Required entrypoint | `<name>/SKILL.md` | `<name>/SKILL.md` |
| Codex discovery | `~/.agents/skills/ai-workflow-shared-<name>` | `~/.agents/skills/ai-workflow-<profile>-<name>` |
| Codex enablement | Every profile and plain Codex | Owning profile, plus explicit manifest inclusions |
| OpenCode discovery | Global `.agents` link or `opencode_config/skills` | Profile skill directory or global `.agents` link |
| OpenCode permission | Allow in general and every intended profile policy | Allow only in intended profile policies |

Keep the directory name and frontmatter `name` equal. Use `agents/openai.yaml`
only for Codex UI metadata; keep `SKILL.md` portable for OpenCode. Add supporting
files only when the workflow needs them. Run the skill validator and then verify
actual discovery.

Do not equate support for several frameworks with shared scope. Infer the
technology set from the component itself, choose one profile-local canonical
source, and use manifest inclusions plus profile permissions for the other
matching technologies. Ask the user when the evidence cannot distinguish a
general capability from a technology-scoped one.

Codex's installer discovers skill directories through
`codex_config/scripts/install.py::managed_skills`, renders profile TOML, and
creates `~/.agents/skills/ai-workflow-*` links. OpenCode profiles default to deny,
so discovery without a matching allow rule is incomplete registration.

## Instructions and rules

- Shared Codex instructions live in `codex_config/shared/instructions/` and are
  loaded by launchers without copying their bodies into profile TOML.
- Profile instructions are listed in that profile's `profile.json`.
- OpenCode rules live below `opencode_config/profiles/<profile>/rules/` and are
  listed in the profile's `opencode.jsonc`.
- Preserve the distinction between prose instructions and executable approval
  rules. Test ordering and deduplication when adding shared guidance.

## Profile or launcher

Adding a Codex profile normally affects the installer `PROFILES` registry,
`profile.json`, instruction sources, overrides, generated config name, Bash and
PowerShell launchers, collision detection, README command tables, and regression
tests. An OpenCode profile affects its config directory, launcher functions,
permission policy, README, and setup tests. Keep Odoo's OpenCode alias mapping to
the Python profile unless the user explicitly changes that architecture.

## Agent

Codex agents are declared through the owning `profile.json` and their referenced
JSON/TOML/instruction files. Validate names, config paths, profile inheritance,
and read-only sandbox behavior. OpenCode agents belong to its profile config or
agent files and need explicit tool and skill permissions.

## Plugin or MCP server

Codex plugin ownership is stored in `codex_config/plugin-profiles.json`; setup
renders enabled state per profile but does not install or authenticate plugins.
MCP configuration belongs in the appropriate source override or OpenCode profile.
Default new external connections to disabled until the required endpoint,
credentials, access boundary, and ownership are defined. Never place secrets in
the repository, README, generated configs, or tests.

## Required closure checks

For every new component:

1. Update `README.md` with the component's purpose, scope, invocation, and any
   changed inventory count or compatibility statement.
2. Update `setup.py` and installer helpers with functional installation, preview,
   inventory, validation, permissions, or launcher behavior. If generic discovery
   is sufficient, make that behavior observable and protect it with a focused
   assertion instead of adding a cosmetic edit.
3. Preview setup and inspect every reported write, link, removal, and package.
4. Run the smallest relevant unit tests, followed by the repository's profile or
   setup verifier when registration changed.
5. Check clean parsing of TOML, JSON/JSONC, YAML frontmatter, Bash, and PowerShell
   files that were touched.
6. Start a new tool session or use a no-model debug/API command to verify actual
   discovery and effective permission.

Do not claim completion from file existence alone. Separate source integration,
generated artifacts, runtime activation, and end-to-end verification in the final
report.
