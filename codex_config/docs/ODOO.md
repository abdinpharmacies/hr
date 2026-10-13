# Native Odoo Profile

Launch `codex-odoo` or `codex --profile odoo` in the working checkout.
The source of truth is `profiles/odoo`; runtime integration consists of a
`~/.codex/odoo.config.toml` symlink, the managed base skill settings and skill
symlinks under `~/.agents/skills`. Plain `codex` keeps its existing behavior.

`profiles/odoo/profile.json` is installer metadata, not a Codex configuration
format. The installer renders `profiles/odoo/config.toml` using native keys and
paths derived from the real installation root. Reinstall after relocating or
changing instruction/skill sources. Relative symlinks are portable; generated
canonical paths avoid ambiguous resolution through the runtime profile symlink.

## Instruction Loading

The installer combines shared `codex-runtime.md`, concise `odoo-core.md`,
conditional `odoo-review-rules.md` and
preexisting base developer guidance into supported `developer_instructions`.
This additive mechanism preserves Codex's built-in instructions. Arbitrary files
in `instructions/` are not auto-discovered. `source-map.md` is an audit reference,
not injected content. `model_instructions_file` was deliberately not chosen
because it replaces built-in model instructions.

Normal repository AGENTS.md discovery remains active. The original ecommerce
AGENTS.md is unchanged, including historical notes/merge markers; it still adds
repository context up to Codex's document limit. This profile does not silently
disable project guidance or copy the giant document into another AGENTS.md.

## On-Demand Workflows

Eight skills: odoo-module-development, odoo19-compatibility,
odoo-security-review, odoo-testing-validation, odoo-translation, bconnect-eplus,
ready-api-enrichment and ab-product-seo-workflow. Each has concise frontmatter
and an entrypoint with links to relevant references. SQL packs, permission
details, commands, schema/Ready facts and Phase 0 metrics stay in references.
Skill metadata is discoverable on launch; bodies/references load when needed.
Shared skill availability is preserved. Other enabled plugins remain inherited.

## Review Rules

| Rule section | Scope |
| --- | --- |
| Security | Effective groups, ACLs, rules, field groups, public methods, sudo and branch/company isolation |
| Architecture | Module ownership, manifests, registry dependencies and integration boundaries |
| B-Connect / E-Plus | SQL, branch predicates, unit/identifier mapping, transactions, queues, idempotency and audit |
| Final Validation | Changed files, compatibility, test/upgrade evidence, translation and packaging gaps |

These former subagent responsibilities now run as conditional instructions in the
main session. Their text is loaded through native `developer_instructions`; only
relevant review checks apply. Review-only requests remain inspection-only, while
authorized implementation/validation work can proceed normally. Rules are guidance,
not a separate read-only sandbox. The four agent TOMLs and role declarations have
been removed. Generic Codex subagent capability and other profiles are unchanged.

## Source Classification and Differences

See [source-map](../profiles/odoo/instructions/source-map.md) for every source
section, line coverage, historical exclusions and adaptations. No OpenCode
runtime, `alwaysApply`, wildcard skill-permission or rule-discovery mechanism is
assumed. Exact native skill entries replace managed wildcard enablement.

Verified corrections are in the compatibility reference. In particular, Owl
supports and/or aliases; Settings blocks support groups; the legacy JS loader
and SQL wrapper remain supported; application JSON-RPC controllers differ from
deprecated external RPC endpoints. Optional runtime dependency checks cannot
replace read-security enforcement. Ready limits/SEO metrics remain historical.

## Maintenance and Validation

Run `python3 scripts/install.py` to review, then `--apply` to install. Existing
changed configuration is backed up; old owned Odoo links are migrated and the
old generic skill retired. A no-op apply creates no backup or installation-file
churn. Credentials and OpenCode files are never installer targets.

Run `python3 tests/verify_profiles.py` and `python3 tests/verify_odoo.py` (the latter
uses PyYAML for frontmatter validation; installation remains standard-library-only).
The first uses an isolated home, native prompt rendering, strict app-server
configuration/skill parsing, migration/idempotence checks and launcher tests.
The second checks the eight skills, frontmatter, links, core size, conditional
review rules, absence of Odoo roles and source mapping. Both tests make no model
requests and require no credentials.

Official mechanisms verified against installed Codex 0.156.1 on 2026-09-24:

- [Profiles](https://learn.chatgpt.com/docs/config-file/config-advanced#profiles)
- [Config keys and role config_file](https://learn.chatgpt.com/docs/config-file/config-reference)
- [Skill discovery](https://learn.chatgpt.com/docs/build-skills)
- [Subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents)
- [Odoo compatibility evidence](../profiles/odoo/skills/odoo19-compatibility/references/compatibility.md)
- [Locally verified Odoo commands](../profiles/odoo/skills/odoo-testing-validation/references/commands.md)
