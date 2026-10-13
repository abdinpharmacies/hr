# Reference audit

Inspected on 2026-09-23. Source commit:
`2293a38c2cd1275c812c9af5793ba2a32f67f407` from
`https://github.com/Mo7amed-fawzy/my_ai_workflow.git`.

## Verified repository facts

- Root `opencode.jsonc` contains the schema and an empty instructions array.
- Four profile directories: flutter, react, node, python. Global is a shared
  rule directory, not a launchable fifth profile.
- All profile configs list `../global/rules/no-comments.md` explicitly.
- Flutter has nine rules, 31 skill directories, and three agent documents.
  React has six rules, three skills, and four optional packages. Node and Python
  each have one rule file and reference absent skill directories.
- The original upstream skill roots hardcoded another user's OpenCode home directory.
- React uses `skills.paths`; the other three use an array for `skills`.
- Node/Python deny `flutter-*` and `dart-*`; React additionally denies
  `react-native-*`; Flutter allows all skills.
- No committed launcher, alias, active-profile state, or profile-selection
  symlink. The only shell scripts are optional Vercel deployment helpers.

## Shell audit on the available machine

Read `~/.bashrc`, `~/.bash_aliases`, and `~/.profile`. `.bashrc` sources
`.bash_aliases` and contains two OpenCode PATH entries. No OpenCode profile
functions, aliases, or OPENCODE_CONFIG/OPENCODE_CONFIG_DIR assignments were found.
The available `~/.config/opencode` contains a root config and package files,
but no profile directories. No shell file was sourced for this audit; sensitive
environment assignments were excluded from recorded output.

The original launchers from the repository author's machine are unavailable.
Their names, environment variables, symlink/copy behavior, and switching behavior
cannot be claimed as verified. The user was asked to supply them. The Codex
conversion does not depend on invented OpenCode launcher behavior.

## Mapping decisions

| OpenCode concept | Codex implementation |
| --- | --- |
| Profile JSONC | Native `<name>.config.toml` overlay and `--profile` |
| Listed Markdown rules | Assembled `developer_instructions`; keep project AGENTS.md discovery |
| Skill directories | Native SKILL.md discovery through stable symlinks |
| Wildcard skill allow/deny | Exact managed SKILL.md enable/disable entries |
| Shared skills | One shared source directory, enabled in each profile |
| Markdown agents | Profile-scoped `[agents.<name>]` + TOML role config files |
| Read-only planning permissions | Read-only sandbox default + agents disabled + scoped instructions |
| Optional React resources | Preserved outside discovery, opt-in only |
| External launchers | New Bash functions forwarding to the native selector |

Codex 0.156.1 is installed. Official documentation confirms profile-v2 files;
`[profiles.<name>]` stopped being supported in 0.134.0. Config-reference role
declarations are used for profile-scoped specialists instead of placing every
specialist in globally discovered `~/.codex/agents`.

## Adaptation details

- The two localization skill files lacked valid frontmatter and overlapped.
  `flutter-setup-localization` is the canonical source for the single adapted
  `flutter-intl-localization` skill. Both original files remain in OpenCode.
- Skill metadata now validates for Codex; unrelated Gemini model hints were
  removed. Compatibility notes move under metadata where needed.
- `flutter-debugging-skill` becomes `flutter-debugging`; shared rebase metadata
  now matches its folder name. References to the shared commit skill are relative.
- Unsupported AskQuestion/MCP assumptions are replaced or qualified by actual
  tool availability. No MCP server is claimed to exist just because a skill
  mentions it.
- Flutter agent examples referencing `cursor_course`, onboarding/workout classes,
  theme tokens, and localization helpers are explicitly conditional on the
  current project. Explicit user requirements outrank reusable conventions.
- Added `node-service-workflow` and `odoo-module-workflow`, and one narrow
  specialist for each of React, Node, and Odoo because upstream has none.
- The final managed set is 38 skills: three shared, 30 Flutter, three React,
  one Node, one Odoo. Optional React resources are not counted as enabled skills.

No model, authentication, provider, MCP, plugin, sandbox, or approval setting is
changed in the parent profiles. The planner role alone adds a read-only default.
