# Codex Rules and Skills Audit

Date: 2026-09-24. Scope: `/home/abdin_02/ai_workflow/codex_config` only.

Reviewed the four profiles, shared instruction sources, all 49 skill entrypoints,
their discovery/loading integration, supporting-resource links, installer and
launchers. Excluded backup snapshots, OpenCode configuration, plugin caches,
credentials and Odoo repository guidance. Historical audit documents are not
active instructions. This is an OpenAI/Codex authoring and integration audit,
not certification of every Flutter, React, Node, Odoo or SQL API example.

## Verdict

Native configuration and skill loading pass. Content is not yet fully aligned:
there are three high-priority deployment-safety findings, a missing reference,
misleading routing metadata, contradictory instructions and avoidable context
cost. The findings below are OPEN. No deployment skill was executed against a
real project, no token values were read, and no deployment occurred.

The preceding Odoo conversion is complete: its four specialist subagents became
conditional main-session review instructions. Flutter's three agents, React's
one agent and Node's one agent remain unchanged. Auditing all profiles did not
expand the Odoo conversion into removal of other profiles' agents.

## Findings

### F01 - P1: Vercel token discovery prints secrets

Evidence: `profiles/react/skills/vercel-cli-with-tokens/SKILL.md:20`, `:28`,
`:42`, `:78`, `:317`. `printenv VERCEL_TOKEN` and broad `.env`/environment greps
emit token values into tool output. This exposes secrets unnecessarily even when
the intended action is only checking authentication availability.

Correction: check presence without printing values; load credentials privately
inside the process and report only set/missing or authentication success/failure.
Ask the user to configure a secret locally, not paste it into conversation.
This is a concrete local safety defect, not a SKILL.md parser violation.

### F02 - P1: Preview deployment can stage unrelated changes and publish production

Evidence: `profiles/react/skills/deploy-to-vercel/SKILL.md:55` and `:67`;
`profiles/react/skills/vercel-cli-with-tokens/SKILL.md:178` and `:185`.
Both routes prefer `git add .`, commit and push without checking the production
branch. The deployment guide itself acknowledges that pushing the production
branch publishes production, conflicting with its preview-only default. Generic
approval to push does not establish approval for unrelated files or production.

Correction: use the direct preview CLI route by default. For an authorized Git
deployment, inspect and stage only intended paths, verify branch/environment,
and bind the result to the specific deployment rather than the latest unrelated
entry. Keep production publication explicitly scoped.

### F03 - P1: Fallback archives include non-dotenv credentials

Evidence: `profiles/react/skills/deploy-to-vercel/resources/deploy-codex.sh:201`
and `:239`; the same logic exists in `resources/deploy.sh:201` and `:239`.
The tar pipeline excludes only `node_modules`, `.git`, `.env` and `.env.*`
before uploading. It can include `.npmrc`, service-account JSON, keys, dumps,
ignored private files and other non-deployment data. Supplied tarballs are also
uploaded without contents validation.

An offline fixture using those exact exclusion arguments confirmed `.env` is
excluded while `.npmrc` and `service-account.json` are included. All fixture
contents were fake; no network request was made.

Correction: build and inspect a deliberately bounded deployment archive, account
for ignore rules and sensitive-file classes, validate supplied archives, and
make the upload destination explicit before transferring project material.
OpenAI's security documentation distinguishes technical permission from safe
workflow design; sandboxing alone is not an archive-content review.
[Agent approvals and security](https://learn.chatgpt.com/docs/agent-approvals-security).

### F04 - P2: Flutter localization references a missing file

Evidence: `profiles/flutter/skills/flutter-intl-localization/SKILL.md:71` and
`:190` both link to `reference.md`, which is absent from that skill directory.
Its prescribed ICU/plural/placeholder workflow therefore cannot load its detail.

Correction: provide the intended material under `references/` and repair both
links, or replace them with verified available references. These are the only
unresolved relative Markdown file-link destinations found by the audit scan.

### F05 - P2: Runtime-debugging skill advertises a different workflow

Evidence: `profiles/flutter/skills/dart-fix-runtime-errors/SKILL.md:3` advertises
live stack traces, LSP and hot reload; `:9` starts a static-analysis guide and
the workflow at `:46` runs analyzer/fix commands. It lacks the advertised live
reproduction and runtime-verification procedure and overlaps static analysis.

Correction: make its description and body agree. Either add a focused runtime
workflow with available-tool fallbacks, or consolidate static guidance into
`dart-run-static-analysis` and route runtime failures to `flutter-debugging`.
Descriptions control implicit selection, so this is functional routing, not
just naming. [Build skills](https://learn.chatgpt.com/docs/build-skills).

### F06 - P2: Loaded rules and workflows contradict each other

Evidence:

- `shared/instructions/no-comments.md:9` forbids unsolicited comments, `:24`
  encourages essential rationale, then `:38` restores the blanket prohibition.
  Flutter/React/Node instructions repeat the stricter wording. Required FFI
  license/generator headers are another conflict with a blanket comment ban.
- `profiles/node/instructions/node-guidelines.md:5` requires ESM specifically
  for an existing CommonJS project, while the Node skill and agent say to preserve
  its module system. This can cause an incidental module-system conversion.
- `profiles/flutter/skills/flutter-apply-architecture-best-practices/SKILL.md:24`
  and `:66` prescribe ChangeNotifier; the data-flow specialist prescribes Cubit/
  BLoC. `flutter-intl-localization` also mandates LocaleCubit for broadly worded
  localization requests. Without task-specific boundaries these can introduce
  competing state-management patterns.
- `profiles/react/skills/react-view-transitions/SKILL.md:24` and `:34` require
  implementing every applicable animation across the app. A request for one
  transition should not silently authorize an app-wide animation pass or a
  prerequisite React release-channel change.

Correction: state a single comment policy with explicit rationale/tooling/license
exceptions, preserve existing Node module systems, and make Flutter architecture
recipes conditional on the selected or established stack. Do not replace the
user's style preference merely to imitate an OpenAI example. Bound the transition
workflow to the requested interaction and verify framework compatibility before
changing dependencies.

### F07 - P2: Six Flutter skill roots load large reference manuals on invocation

Evidence: `flutter-debugging/SKILL.md` is 1,056 lines; root/jailbreak is 1,085;
sqlite3 is 947; local-persistence is 729; sqflite is 582; checks migration is 528.
Except for debugging's source index, these have no `references/` split. A narrow
invocation loads platform branches, recipes and examples unrelated to that task.
This is not a hard Codex size-limit failure: all six parse and are discoverable.

Correction: retain short workflow routers; move platform guides, API examples,
migration mappings and package-selection tables into focused references. Keep
the knowledge, change when it enters context. Odoo's eight skills already use
this pattern. OpenAI recommends minimal routers and task-relevant supporting
material. [Skill and prompt guidance](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra).

### F08 - P3: Several descriptions are broader than their workflows

Evidence: `shared/skills/find-skills/SKILL.md:3` includes generic "how do I do X";
`dart-build-cli-app/SKILL.md:3` says command-line utilities without naming Dart;
`dart-use-pattern-matching/SKILL.md:3` omits language and concrete triggers;
`flutter-use-http-package/SKILL.md:3` covers REST work generically. Widget preview
and root/jailbreak descriptions can also select their specialized workflows for
ordinary UI or general mobile security work.

Correction: front-load the language and exact job; add exclusions where neighboring
skills overlap. Keep discovery focused on finding/installing skills, not normal
implementation questions. Test positive and negative prompts. This is a routing
risk inferred from the text; no live model trigger benchmark was run.
[Build skills](https://learn.chatgpt.com/docs/build-skills).

The find-skills install route is a third-party `npx skills` workflow, not Codex's
native skill-installer. Its popularity counts and star thresholds are mutable and
do not substitute for reviewing a package's instructions/scripts before installing.

### F09 - P3: Imported capability references are not self-contained

Evidence: `shared/skills/writing-guidelines/SKILL.md:29` and
`profiles/react/skills/web-design-guidelines/SKILL.md:29` prescribe `WebFetch`.
It is not a universally provided Codex tool. Shared runtime instructions mitigate
this, but the skill body still assumes a specific host capability.
`profiles/flutter/skills/flutter-local-persistence/SKILL.md:592` names
`local-db-architect`, which is not declared by any of these profile manifests.

Correction: use an available web/HTTP tool with a clear unavailable-network path;
describe the persistence review as main-session steps unless an actual matching
agent is present. Optional `agents/openai.yaml` can declare genuine dependencies;
its absence alone is not an error. Do not invent tools or agents to satisfy prose.

### F10 - P3: README inventory no longer matches installed resources

Evidence: `README.md:46` omits shared writing-guidelines; `:57` describes three
React skills and `:59` an optional four-package directory. The active layout has
six React skills and no `profiles/react/optional` directory. Native tests discover
ten React-profile skills including the four shared skills.

Correction: regenerate the README inventory from the current manifests/directories.
Treat old audit snapshots as historical, not a description of current activation.

## Match to OpenAI Documentation

| Area | Result |
|---|---|
| Native profiles | PASS: separate `<profile>.config.toml` layers; native `--profile` loading verified. |
| Effective instructions | PASS: installer assembles declared Markdown into supported `developer_instructions`. Arbitrary `instructions/` files are not assumed to load. |
| Skills | PASS: 49 valid name/description frontmatters, matching directory names; no duplicate names within this tree. |
| Discovery/isolation | PASS: native scanning of installed links and profile-specific enable/disable entries. |
| Supporting material | PARTIAL: local references resolve except F04; large roots need F07. |
| Review rules | PASS: Odoo review prose is loaded as instructions, not confused with command permissions. |
| Remaining agents | PASS: five config_file declarations and their TOML targets parse; Odoo has none. |
| Behavioral activation | NOT BENCHMARKED: loader tests do not prove correct skill selection for every prompt. |

Separate profile files are documented for current Codex; the installer enforces
the documented minimum version. [Advanced configuration](https://learn.chatgpt.com/docs/config-file/config-advanced#profiles).

`developer_instructions` and `[agents.<name>].config_file` remain supported in the
configuration reference. Do not mistake the newer standalone-agent discovery
schema for a requirement on these explicitly referenced config layers.
[Configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).

Markdown review rules are behavioral instructions. Native `*.rules` files use
command-prefix policies; converting Odoo review prose into those files would
change its meaning. [Native rules](https://learn.chatgpt.com/docs/agent-configuration/rules).

## Validation Performed

- `python3 tests/verify_odoo.py`: PASS, including zero Odoo agent declarations,
  both instruction sources, eight skill frontmatters and Odoo reference paths.
- `python3 tests/verify_profiles.py`: PASS for base, Flutter, React, Node and Odoo:
  native prompt rendering, strict config parsing, skills/list, instruction
  isolation, launcher argument preservation, collision handling, migration,
  second-install idempotency and uninstall preservation in isolated temporary homes.
- All 10 active TOML files parse; all 20 loaded instruction sources appear in
  their generated profile layers. The 21st source, Odoo source-map, is reference-only.
- All 49 skill frontmatters parse. The relative-link scan found F04; therefore
  this report does NOT claim every reference path passed.
- `bash -n shell/launchers.bash`: PASS.
- Portable-source scan found no literal foreign-user home paths in active
  Markdown, manifests, scripts or launchers. Generated absolute paths are for
  this installation and are recomputed by the installer.
- F03 reproduced offline using fake archive fixtures only.
- No live deployments, framework/example execution, paid model evals, database
  upgrades, global reinstall, credential changes or OpenCode changes in this audit.

## Context Footprint

These are generated developer-instruction words/UTF-8 bytes, not tokenizer counts
or total session size. They exclude built-in instructions, working-project
guidance, tool metadata and the skill catalog.

| Profile | Always-loaded words | Bytes | Own skills | With shared | Custom agents |
|---|---:|---:|---:|---:|---:|
| Flutter | 1,648 | 12,194 | 30 | 34 | 3 |
| React | 1,200 | 8,172 | 6 | 10 | 1 |
| Node | 640 | 4,209 | 1 | 5 | 1 |
| Odoo | 913 | 7,020 | 8 | 12 | 0 |

Odoo core is 385 words; its new conditional review rules are 387 words. The
remaining 141 words are shared runtime guidance and the profile marker.
Skill bodies and references remain on demand. Plain Codex exposes zero skills
managed by this package in the isolated test, not zero skills from every possible
external source. External plugin/system catalogs were outside this review.

## Completed Odoo Conversion

Launch: `codex-odoo` or `codex --profile odoo`.

Changed sources: Odoo `profile.json`, new `instructions/odoo-review-rules.md`,
`instructions/source-map.md`, security/testing/B-Connect skill entrypoints;
removed the four former Odoo agent TOMLs. Updated generated Odoo `config.toml`,
README, `docs/ODOO.md`, `docs/ODOO_VALIDATION.md`, and both profile tests.

The four review areas are security, module architecture, B-Connect correctness
and final validation. They now run in the main session as relevant. Independent
agent contexts and agent-specific read-only sandboxes are not reproduced by
instruction text. The main session still obeys its configured permissions.

The conversion was backed up under
`backups/odoo-review-rules-20260924-104415`. A second installation had no planned
writes, symlink changes or removals. The audit adds only its report and inventory;
it does not silently remediate F01-F10 or change the other profiles' behavior.

## Resource Inventory

The companion `CODEX_RESOURCE_INVENTORY.json` records every skill and instruction
source, sizes, metadata, profile totals and structural scan results. The following
tables cover every entrypoint; "No additional issue" means no additional Codex
authoring/integration finding in this review, not a framework API certification.

### All 49 Skills

| Group | Skill | Lines | Review note |
|---|---|---:|---|
| shared | [find-skills](../shared/skills/find-skills/SKILL.md) | 144 | F08 |
| shared | [git-commit](../shared/skills/git-commit/SKILL.md) | 300 | No additional issue |
| shared | [git-interactive-rebase](../shared/skills/git-interactive-rebase/SKILL.md) | 387 | No additional issue |
| shared | [writing-guidelines](../shared/skills/writing-guidelines/SKILL.md) | 39 | F09 |
| flutter | [dart-add-unit-test](../profiles/flutter/skills/dart-add-unit-test/SKILL.md) | 124 | No additional issue |
| flutter | [dart-build-cli-app](../profiles/flutter/skills/dart-build-cli-app/SKILL.md) | 186 | F08 |
| flutter | [dart-collect-coverage](../profiles/flutter/skills/dart-collect-coverage/SKILL.md) | 141 | No additional issue |
| flutter | [dart-fix-runtime-errors](../profiles/flutter/skills/dart-fix-runtime-errors/SKILL.md) | 167 | F05 |
| flutter | [dart-generate-test-mocks](../profiles/flutter/skills/dart-generate-test-mocks/SKILL.md) | 157 | No additional issue |
| flutter | [dart-migrate-to-checks-package](../profiles/flutter/skills/dart-migrate-to-checks-package/SKILL.md) | 528 | F07 |
| flutter | [dart-resolve-package-conflicts](../profiles/flutter/skills/dart-resolve-package-conflicts/SKILL.md) | 117 | No additional issue |
| flutter | [dart-run-static-analysis](../profiles/flutter/skills/dart-run-static-analysis/SKILL.md) | 110 | No additional issue |
| flutter | [dart-setup-ffi-assets](../profiles/flutter/skills/dart-setup-ffi-assets/SKILL.md) | 426 | F06 (license headers) |
| flutter | [dart-use-doc-examples](../profiles/flutter/skills/dart-use-doc-examples/SKILL.md) | 97 | No additional issue |
| flutter | [dart-use-ffigen](../profiles/flutter/skills/dart-use-ffigen/SKILL.md) | 225 | F06 (license headers) |
| flutter | [dart-use-pattern-matching](../profiles/flutter/skills/dart-use-pattern-matching/SKILL.md) | 146 | F08 |
| flutter | [dart-use-primary-constructors](../profiles/flutter/skills/dart-use-primary-constructors/SKILL.md) | 264 | No additional issue |
| flutter | [dart-write-documentation](../profiles/flutter/skills/dart-write-documentation/SKILL.md) | 139 | No additional issue |
| flutter | [flutter-add-integration-test](../profiles/flutter/skills/flutter-add-integration-test/SKILL.md) | 170 | No additional issue |
| flutter | [flutter-add-widget-preview](../profiles/flutter/skills/flutter-add-widget-preview/SKILL.md) | 147 | F08 |
| flutter | [flutter-add-widget-test](../profiles/flutter/skills/flutter-add-widget-test/SKILL.md) | 156 | No additional issue |
| flutter | [flutter-apply-architecture-best-practices](../profiles/flutter/skills/flutter-apply-architecture-best-practices/SKILL.md) | 163 | F06 |
| flutter | [flutter-build-responsive-layout](../profiles/flutter/skills/flutter-build-responsive-layout/SKILL.md) | 141 | No additional issue |
| flutter | [flutter-debugging](../profiles/flutter/skills/flutter-debugging/SKILL.md) | 1056 | F07 |
| flutter | [flutter-fix-layout-issues](../profiles/flutter/skills/flutter-fix-layout-issues/SKILL.md) | 132 | No additional issue |
| flutter | [flutter-implement-json-serialization](../profiles/flutter/skills/flutter-implement-json-serialization/SKILL.md) | 154 | No additional issue |
| flutter | [flutter-intl-localization](../profiles/flutter/skills/flutter-intl-localization/SKILL.md) | 191 | F04, F06 |
| flutter | [flutter-local-persistence](../profiles/flutter/skills/flutter-local-persistence/SKILL.md) | 729 | F07, F09 |
| flutter | [flutter-obfuscation](../profiles/flutter/skills/flutter-obfuscation/SKILL.md) | 289 | No additional issue |
| flutter | [flutter-root-jailbreak-detection](../profiles/flutter/skills/flutter-root-jailbreak-detection/SKILL.md) | 1085 | F07, F08 |
| flutter | [flutter-setup-declarative-routing](../profiles/flutter/skills/flutter-setup-declarative-routing/SKILL.md) | 257 | No additional issue |
| flutter | [flutter-sqflite](../profiles/flutter/skills/flutter-sqflite/SKILL.md) | 582 | F07 |
| flutter | [flutter-sqflite3](../profiles/flutter/skills/flutter-sqflite3/SKILL.md) | 947 | F07 |
| flutter | [flutter-use-http-package](../profiles/flutter/skills/flutter-use-http-package/SKILL.md) | 175 | F08 |
| node | [node-service-workflow](../profiles/node/skills/node-service-workflow/SKILL.md) | 17 | No additional issue |
| odoo | [ab-product-seo-workflow](../profiles/odoo/skills/ab-product-seo-workflow/SKILL.md) | 35 | No additional issue |
| odoo | [bconnect-eplus](../profiles/odoo/skills/bconnect-eplus/SKILL.md) | 30 | No additional issue |
| odoo | [odoo-module-development](../profiles/odoo/skills/odoo-module-development/SKILL.md) | 38 | No additional issue |
| odoo | [odoo-security-review](../profiles/odoo/skills/odoo-security-review/SKILL.md) | 31 | No additional issue |
| odoo | [odoo-testing-validation](../profiles/odoo/skills/odoo-testing-validation/SKILL.md) | 30 | No additional issue |
| odoo | [odoo-translation](../profiles/odoo/skills/odoo-translation/SKILL.md) | 24 | No additional issue |
| odoo | [odoo19-compatibility](../profiles/odoo/skills/odoo19-compatibility/SKILL.md) | 27 | No additional issue |
| odoo | [ready-api-enrichment](../profiles/odoo/skills/ready-api-enrichment/SKILL.md) | 23 | No additional issue |
| react | [composition-patterns](../profiles/react/skills/composition-patterns/SKILL.md) | 87 | No additional issue |
| react | [deploy-to-vercel](../profiles/react/skills/deploy-to-vercel/SKILL.md) | 296 | F02, F03 |
| react | [react-best-practices](../profiles/react/skills/react-best-practices/SKILL.md) | 152 | No additional issue |
| react | [react-view-transitions](../profiles/react/skills/react-view-transitions/SKILL.md) | 337 | F06 |
| react | [vercel-cli-with-tokens](../profiles/react/skills/vercel-cli-with-tokens/SKILL.md) | 353 | F01, F02 |
| react | [web-design-guidelines](../profiles/react/skills/web-design-guidelines/SKILL.md) | 39 | F09 |

### All Instruction Sources

| Source | Words | Loading and review note |
|---|---:|---|
| [shared/instructions/codex-runtime.md](../shared/instructions/codex-runtime.md) | 136 | Loaded by all four profiles; no additional issue |
| [shared/instructions/no-comments.md](../shared/instructions/no-comments.md) | 316 | Loaded; F06 |
| [profiles/flutter/instructions/flutter-assets.md](../profiles/flutter/instructions/flutter-assets.md) | 74 | Loaded by its profile; no additional issue |
| [profiles/flutter/instructions/flutter-code-quality.md](../profiles/flutter/instructions/flutter-code-quality.md) | 94 | Loaded by its profile; no additional issue |
| [profiles/flutter/instructions/flutter-custom-widgets.md](../profiles/flutter/instructions/flutter-custom-widgets.md) | 405 | Loaded; optional improvement: move extended examples to references |
| [profiles/flutter/instructions/flutter-dependencies.md](../profiles/flutter/instructions/flutter-dependencies.md) | 60 | Loaded by its profile; no additional issue |
| [profiles/flutter/instructions/flutter-forms.md](../profiles/flutter/instructions/flutter-forms.md) | 55 | Loaded by its profile; no additional issue |
| [profiles/flutter/instructions/flutter-input-model.md](../profiles/flutter/instructions/flutter-input-model.md) | 268 | Loaded; optional improvement: move extended examples to references |
| [profiles/flutter/instructions/flutter-response-style.md](../profiles/flutter/instructions/flutter-response-style.md) | 82 | Loaded; F06 |
| [profiles/flutter/instructions/flutter-widgets.md](../profiles/flutter/instructions/flutter-widgets.md) | 73 | Loaded by its profile; no additional issue |
| [profiles/flutter/instructions/obfuscation-safe-code.md](../profiles/flutter/instructions/obfuscation-safe-code.md) | 80 | Loaded by its profile; no additional issue |
| [profiles/node/instructions/node-guidelines.md](../profiles/node/instructions/node-guidelines.md) | 183 | Loaded; F06 |
| [profiles/odoo/instructions/odoo-core.md](../profiles/odoo/instructions/odoo-core.md) | 385 | Loaded by its profile; no additional issue |
| [profiles/odoo/instructions/odoo-review-rules.md](../profiles/odoo/instructions/odoo-review-rules.md) | 387 | Loaded by its profile; no additional issue |
| [profiles/odoo/instructions/source-map.md](../profiles/odoo/instructions/source-map.md) | 1301 | Reference only, not injected |
| [profiles/react/instructions/agent-workflow.md](../profiles/react/instructions/agent-workflow.md) | 144 | Loaded; F06 |
| [profiles/react/instructions/architecture.md](../profiles/react/instructions/architecture.md) | 103 | Loaded by its profile; no additional issue |
| [profiles/react/instructions/performance.md](../profiles/react/instructions/performance.md) | 112 | Loaded by its profile; no additional issue |
| [profiles/react/instructions/react-guidelines.md](../profiles/react/instructions/react-guidelines.md) | 195 | Loaded; F06 |
| [profiles/react/instructions/typescript.md](../profiles/react/instructions/typescript.md) | 92 | Loaded by its profile; no additional issue |
| [profiles/react/instructions/ui-accessibility.md](../profiles/react/instructions/ui-accessibility.md) | 97 | Loaded by its profile; no additional issue |
