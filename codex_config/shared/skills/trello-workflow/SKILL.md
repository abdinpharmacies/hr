---
name: trello-workflow
description: Draft, organize or update Trello boards, cards, checklists and task items using project terminology and user-facing task wording.
---

# Trello Workflow

Apply only to explicitly authorized Trello work. Availability of a connector or this reference does not authorize sending updates.

Identify the requested board, card and checklist from supplied context. Inspect
existing items when a connector is available; do not invent IDs or assume a
particular tool exists. Ask only for missing target details. Draft locally when
no suitable connector is available. Distinguish proposed wording from saved
changes, avoid duplicate items, and report exactly what was changed. Do not
mark work done solely because a commit exists.

## Trello Workflow Rules

When using Trello, use the correct Trello terms and write items like an experienced project manager:

- `Board` means the project/workspace board.
- `List` or `Column` means a board column such as `in plan`, `in progress`, or `docs`.
- `Card` means the main task or feature, such as `smart transfer`.
- `Section` means a checklist inside a card, such as `to do` or `Bugs`.
- `Task` or `Item` means a checklist item inside a section.
- `Done` means marking the card or checklist item complete, or moving it to the agreed done list when one exists.

Trello task wording rules:

- Use plain user-facing task titles, not raw commit messages.
- Do not put commit hashes in checklist item titles unless the user explicitly asks.
- Start checklist items with an action verb: `Add`, `Fix`, `Remove`, `Translate`, `Validate`, `Document`, `Refactor`.
- Mention the feature or screen affected, not only the technical module name.
- Keep module technical names only when they add clarity.
- Prefer `Remove Excel file import from Smart Transfer wizard` over `ab_transfer_smart/chore: remove add excel sheet (hash)`.
- If commit details are useful, place them in a card comment or description, not the checklist item title.
