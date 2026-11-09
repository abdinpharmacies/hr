---
name: software-design
description: Design and explain software or create substantial personal and work designs. Use for architecture, flows, performance, diagrams, visual reports, guides, presentations, infographics, and PDFs grounded in evidence. Skip routine code edits and simple answers.
---

# Software design

Help the user understand or decide something about software, or create a clear visual artifact for personal or work use. Match the scope to the request: a screen, feature, module, system, report, guide, slide deck, infographic, or PDF. A new proposal or artifact does not require an existing repository or a full architecture audit.

## Route only what is needed

Read only the matching reference, then any supporting reference required by the deliverable. Do not load every reference or run repository analysis by default.

| Request | Read | Default scope |
| --- | --- | --- |
| Explain current code, dependencies, state or request flow | [Understand](references/understand.md) | The named part and its direct collaborators |
| Suggest a split, refactor, feature design or alternative | [Propose](references/propose.md) | The decision and affected boundaries |
| Investigate latency, rendering, memory or throughput | [Performance](references/performance.md) | One scenario and its critical path |
| Show what each person does and sees across a feature | [Diagrams](references/diagrams.md) and [Usage flow](references/flows/usage.md) | Actors, actions and visible outcomes |
| Show how software components communicate and move data | [Diagrams](references/diagrams.md) and [System flow](references/flows/system.md) | Verified runtime boundaries and interactions |
| Create, edit, render or export another software diagram | [Diagrams](references/diagrams.md) | Text and/or rendered image, matched to the request |
| Write or review an explanation or design document | [Writing](references/writing.md) | The requested prose |
| Design a polished report, training guide, PDF, presentation, infographic or other work visual | [Visual artifacts](references/artifacts/visual-artifacts.md) and [Writing](references/writing.md) when substantial prose is needed | The audience, source evidence and requested format |
| Explicit Vercel writing handbook audit | [Writing audit](references/writing-audit.md) | Supplied files |

Mixed requests combine only relevant routes. For a visual design recommendation, use Propose and Diagrams; do not run Understand's repository-wide tooling unless needed. Load Writing for substantial prose or a writing review, not every short response. A visual artifact can use the relevant format and design skills when available; this skill coordinates the evidence, audience, layout choice and final review. For Arabic operational reports and training PDFs, start with the supplied Odoo-guide visual reference in Visual artifacts unless the user requests another style.

## Shared workflow

1. Infer the target, audience, current question and available evidence from the conversation. Continue the ongoing task; do not restart discovery or ask already answered questions. Ask only when a missing detail changes the recommendation materially.
2. Inspect the relevant source/configuration or supplied artifacts. Label current observations, inferred behavior, proposed changes, and unknowns separately. Record the revision and environment when they matter; source inspection alone does not prove deployed behavior.
3. Explain responsibility, ownership and relationships. Tie current-state claims to evidence and recommendations to an observed problem or explicit requirement. A component's present function does not prove its historical design rationale.
4. Choose the requested output. For visual software explanations and design/split proposals, include a focused diagram unless the user requests text only. Default to a plain-character text diagram for a general diagram request. Generate PNG/SVG for diagrams only on an explicit image or format request. For a requested report, guide, presentation, infographic or PDF, follow Visual artifacts and deliver the finished file. Analysis or proposals do not authorize implementation, remote publication, package installation or active production tests.
5. Validate the chosen deliverable. Inspect every rendered page or image before delivery, and correct clipping, missing glyphs, direction, spacing and misleading visual emphasis. State relevant uncertainty and the next measurement or decision that would resolve it. Do not claim performance gains or visual quality without the corresponding checks.

Keep usage flows and system flows distinct. A usage flow follows people and their actions; a system flow follows technical calls, data and state changes. Preserve the user's chosen type and keep two views separate when both are requested. The accepted eCommerce usage-flow image is a visual example, not a source of architecture facts or a fixed template for other projects.

Use the user's language for explanations while preserving code identifiers. Keep current and proposed views visibly distinct. Do not invent infrastructure, services, queues, state layers or design rationale to make a diagram look complete.

## Optional resources

`resources/c4/` retains the repository analyzer and model renderer; load the procedure linked from Understand only for a repository architecture report. `resources/diagrams/` retains rendering scripts, lockfile, format references and example galleries; load the relevant renderer instructions through Diagrams. These are supporting tools, not separately discoverable skills. Tools may require Python 3.11+, Node.js, Java or other renderers; check only the requirements of the selected path. Do not bootstrap the entire toolchain for one diagram.
