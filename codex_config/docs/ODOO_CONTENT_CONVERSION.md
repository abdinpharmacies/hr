# Odoo Content Conversion Review

Reviewed 2026-09-24 against the repository AGENTS.md (1,595 lines, SHA-256
`2f630668146d94cdeab3b4c9ebb415b9ff01075de551142bf442dfc620d6d66a`).
Scope: Odoo conversion and its general Trello workflow, not unrelated profiles.

## Result

All source sections have a destination in effective instructions, focused skills
or their references. No content-bearing section is left only in the source.
This is a semantic conversion, not a duplicate of the giant AGENTS.md: concise
rules retain invariants; detailed examples, measurements and history stay on demand.
Incorrect or overgeneralized technical claims remain explicitly corrected.

- Restored the complete first B-Connect SQL query in query-patterns.md and removed
  its incomplete fragment from schema.md. All three original SQL blocks remain
  intact, alongside the existing branch/consistency/parameterization warnings.
- Restored stable XML-ID references instead of hardcoded database row IDs.
- Made the no-unnecessary-database-edits/triggers rule explicit and retained the
  final new-module developer/author verification.
- Moved Trello vocabulary and task wording into a directly discoverable shared
  trello-workflow skill; there is no duplicate old Trello reference.
- Preserved repository status tables, compatibility session notes, the original
  SEO architecture brief, and both module UI session histories in topic-specific
  references. Historical actions are not permission to replay them.
- Preserved archival and pricing examples, including the suggested price-history
  model and its four audit fields, in the module-development references.
- Recorded merge-conflict delimiters as provenance in the coverage inventory;
  both branches' content is retained without active conflict markers.

## Organization

The Odoo profile still has eight specialist skills and no custom subagents.
Four former reviewer roles remain conditional instructions in the main session.
Twenty Odoo reference files are linked from the relevant skills. The shared
Trello skill also applies to other profiles; plain Codex remains the normal default.

The core and conditional review instructions are always loaded by the Odoo
profile. Skill names/descriptions are discovery metadata; skill bodies and
references load when relevant. Coverage metadata and historical excerpts are
not added to the effective profile instructions. Repository AGENTS.md discovery
is unchanged; this conversion does not remove that file's separate context cost.

This follows [OpenAI skill guidance](https://learn.chatgpt.com/docs/build-skills):
focused descriptions, progressive disclosure, linked references and native
discovery. Behavioral instructions are not command-permission
[.rules files](https://learn.chatgpt.com/docs/agent-configuration/rules).

## Validation

```bash
python3 tests/verify_odoo.py --source /opt/odoo19/custom-addons-ecommerce/AGENTS.md
python3 tests/verify_profiles.py
```

Checks cover frontmatter, TOML, links, balanced code fences, all source ranges,
source hash, preserved verbatim sections, historical excerpts, exact SQL blocks,
reference reachability, native profile selection, strict config/skill discovery,
instruction isolation, zero Odoo agents, launchers and installer idempotence.
Source mapping is a review record, not a claim that automated range coverage
alone proves the meaning of every paraphrase. No live Odoo/database/API operation
is needed for these tests. Live model skill-routing behavior is not benchmarked.

The source map and content-coverage.json are the maintained conversion index.
Older all-profile audit files remain historical snapshots; this report records
the follow-up Odoo content corrections only.
