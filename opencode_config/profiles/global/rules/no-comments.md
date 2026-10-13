---
description: Comments policy. Do NOT add comments to code unless the user explicitly asks. Covers inline, block, and doc comments. Preserve existing meaningful comments when editing. Relax only at explicit user request.
alwaysApply: true
---
# Comments Policy

This rule controls comment usage in all generated or edited code.

## The Rule

No comments unless the user explicitly asks.

- Do NOT add comments to code unless the user explicitly asks you to.
- This applies to inline comments, block comments, doc comments, and "explaining" comments alike, absent a specific request.

## Detailed Guidance

- When you write code (widgets, functions, logic), do not sprinkle explanatory `//` comments over it.
- Do not add comments that restate what the code already says:

  ```dart
  // increment counter
  count++;   // AVOID — the code is self-evident
  ```

- Do not add "signature" comments, "auto-generated" boilerplate comments, or gratuitous section dividers unless the user asks — except where required to keep tooling/lints happy (e.g., `// ignore:` directives in rare cases, or LEGACY header comments you are explicitly told to preserve).
- Prefer self-documenting code: choose descriptive names (see Code Quality rule) so the code reads clearly without comments.
- If a piece of logic is genuinely non-obvious (e.g., a subtle algorithm, a non-trivial workaround, or a unit conversion with a reason), a brief comment IS acceptable and encouraged to explain WHY. The rule targets redundant or decorative comments, not essential rationale.

## When the User Asks for Comments

- If the user explicitly requests comments (e.g., "add doc comments", "annotate this function"), then add them — follow standard conventions:
  - Public APIs: doc comments (`///`) describing purpose, parameters, and return value.
  - Inline rationale comments only where they add value.
- Match the existing style used elsewhere in the file/project.

## When Editing Existing Code

- Preserve existing meaningful comments in code you modify unless the user asks you to remove them.
- Do not remove comments that encode important decisions or context already present in the codebase.

Apply this rule strictly by default; relax it only at the explicit request of the user.
