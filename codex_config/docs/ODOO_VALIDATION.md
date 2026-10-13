# Odoo Profile Validation

## Current Update: Review Rules

The four Odoo subagents have been converted into conditional main-session rules
in `profiles/odoo/instructions/odoo-review-rules.md`. The profile manifest loads
this file with the core through `developer_instructions`, and declares no custom
agents. Skills now point to the main-session review workflow. The original
subagent smoke-test results below are historical and describe the earlier setup.
Current checks validate rule loading, zero Odoo roles, skills and idempotence.
Other profiles, OpenCode, credentials and the existing launcher are unchanged.

## Original Subagent Installation

Completed 2026-09-24 with Codex CLI 0.156.1 and local Odoo 19.0.

## Results

- Native `codex --profile odoo debug prompt-input` rendered the exact core in
  both a neutral directory and the ecommerce repository.
- All eight Odoo skills were present in rendered discovery metadata and enabled
  by native `skills/list`; the profile also enables four shared managed skills.
- Strict app-server parsing passed for the generated layer and each of the four
  native reviewer TOMLs. All declared config_file and skill paths exist.
- Live ephemeral read-only `codex exec --profile odoo` smoke test exited 0 and
  reported all four exact custom role types spawned and completed. Each returned
  its expected narrow scope. No role task requested file/database actions.
  The session exposed no close-agent tool; all tasks finished before CLI exit.
- Native CLI `app-server` does not accept `--profile`; strict schema checks used
  the same layer in a temporary Codex home. Actual profile selection was checked
  through supported CLI prompt rendering and the live exec smoke test.
- All generated TOML parsed successfully. All eight skill frontmatters passed
  the bundled skill-creator validator and `tests/verify_odoo.py`.
- All local Markdown reference links resolve. The profile contains 16 focused
  skill references and a complete source-section/line-range classification.
- Tests covered all four profiles, preserved base developer guidance, managed
  skill isolation, native agent declarations, paths with spaces, argument
  forwarding, legacy Odoo link migration, collision refusal and uninstall.
- A second real `install.py --apply` returned empty write/symlink/removal lists.
  Isolated tests also verified no backup or installation-record churn on no-op.
- `codex-odoo` remains the existing function invoking `command codex --profile odoo`;
  plain `codex` remains the existing binary. No launcher edit was necessary.
- Hashes of 3,632 protected files were unchanged, including the inspected
  OpenCode trees, Codex/OpenCode credential files, .bashrc and source AGENTS.md.
  Unmanaged Codex base configuration matches its pre-install backup semantically.
- Active Odoo sources/configuration contain no other user's home paths. A literal
  old-user path in the historical audit was replaced with a descriptive note.

## Context Footprint

Odoo core: 385 words, 3,033 bytes including final newline. Effective additive
profile guidance including shared runtime instructions: 526 words, 4,022 bytes.
SQL packs, schema details, Ready notes and Phase 0 metrics are not injected there.
Skill names/descriptions and role descriptions are available for discovery;
bodies/references load on demand.

Native prompt text measured 32,251 bytes in a neutral directory and 65,798 bytes
in the ecommerce repository. Those totals include inherited Codex instructions,
skills/plugins and repository guidance, not just this profile. The original
large AGENTS.md still loads separately up to Codex's document-size limit; it was
not overwritten, duplicated inside this profile, or silently disabled.

## Odoo Evidence and Limits

Official 19.0 ORM/views/actions/security/assets/JS/testing/CLI/translation docs
were checked, with installed source used to resolve stale examples. Owl rules
were checked against official v2.8.2 documentation and the installed parser.
The compatibility reference records corrected historical claims.

Local server/i18n help confirms documented commands. Config metadata and ports
were inspected without starting/stopping Odoo or upgrading a database. The normal
config points at a different addons checkout, so the workflow requires an explicit
addons-path check. This profile task did not run module business tests or database
upgrades; the documented commands are validated syntax, not claimed test runs.

Ready API endpoints/account limits were not invented; historical quota/trial
observations remain references requiring verification for actual integration.
SEO Phase 0 counts remain historical. No ab_product_seo implementation was found
in this checkout; its skill preserves the source architecture as intended design.

## Changed Files

- `profiles/odoo/config.toml`, `profile.json`, `instructions/odoo-core.md` and
  `instructions/source-map.md`.
- Four reviewer files in `profiles/odoo/agents/`.
- Eight `profiles/odoo/skills/*/SKILL.md` files and 16 skill references.
- `scripts/install.py`, `scripts/uninstall.py`, `scripts/import_opencode.py`.
- `tests/verify_profiles.py`, `tests/verify_odoo.py`.
- `README.md`, `docs/ODOO.md`, this validation record and the old-user audit note.
- Generated base fragment and other profile layers changed only their managed
  Odoo skill entries. Runtime base managed entries and symlinks were updated.
- Retired old Odoo generic guidance, broad engineer role and generic skill;
  backed up outside the profile with the other changed sources/configuration.

Backups are under `codex_config/backups/`; `installation.json` records the runtime
config backup. See source-backup `change-plan.json` for exact source paths.
