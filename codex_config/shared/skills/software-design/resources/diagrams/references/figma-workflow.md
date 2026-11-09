# Figma/FigJam workflow
Use this reference when a diagram must be created, redrawn, or collaboratively edited in Figma or FigJam. Figma is an editable delivery target and collaboration surface; it is not a replacement for the canonical DSL/SVG source or the repository's local renderer.

## Choose the path

| User request | Preferred path | Result |
| --- | --- | --- |
| Create a new flow, sequence, state, ER, or Gantt diagram in FigJam | `generate_diagram` | A new editable FigJam diagram from Mermaid |
| Put an existing Mermaid/PlantUML/D2/Graphviz/draw.io result into Figma | Render locally, then import SVG or rebuild the structure | A Figma file plus the original source and local output |
| Redraw an existing diagram in a Figma/FigJam file | Inspect the file first, then use incremental edits | The existing file is updated without losing unrelated content |
| Add notes, callouts, colors, or a legend to a generated diagram | Generate or import the base structure, then use `use_figma` | A composed, editable board |
| Implement a Figma diagram as application code | Use the separate design-to-code workflow | Code in the target repository; no write-back to Figma |

Do not use a screenshot as the only source for a diagram that must remain editable. If the only available input is a screenshot, state that the structure will need to be reconstructed and preserve the screenshot as a visual reference.

## Source and file contract

Before touching Figma, record:

- the canonical source path and its DSL;
- the local rendered output used as the visual baseline;
- the Figma or FigJam URL and, when available, its `fileKey`;
- whether the Figma file is a new artifact, an imported copy, or an update to an existing file;
- the intended local outputs and documents that still need to be generated.

Keep the DSL, draw.io XML, or SVG source in the repository when it is available. Store the Figma URL in the project document or delivery note, not in place of the source. A Figma link is remote collaboration state and cannot make a clean checkout reproducible.

For a multi-diagram project, keep the existing JSON manifest focused on local sources, renderers, outputs, and documents. Add Figma links as delivery metadata in the project documentation unless the project defines a separate schema for remote artifacts.

## Create a new FigJam diagram

Use `generate_diagram` when the requested structure is supported by its Mermaid input: `flowchart`, `sequenceDiagram`, `stateDiagram`/`stateDiagram-v2`, `erDiagram`, or `gantt`.

1. Load the `figma-generate-diagram` skill before calling `generate_diagram`. If the board needs follow-up API edits, also load `figma-use` and `figma-use-figjam` before calling `use_figma`.
2. Build Mermaid from the canonical model. Use stable camelCase IDs, quoted labels for special characters, and no emojis, HTML, or literal `\\n` escapes.
3. Pass a descriptive `name`, the Mermaid source, and a short `userIntent`. If the user supplied an existing FigJam file, pass its `fileKey` so the new diagram is added there.
4. Return the generated board link and record it beside the source/output mapping.
5. Use `use_figma` only for follow-up edits that Mermaid generation cannot express, such as callouts, annotations, or custom coloring.

`generate_diagram` does not support every diagram type and does not provide reliable node-by-node editing of an existing generated diagram. For unsupported types or precise layout edits, use the import or incremental-edit paths below.

When iterating on the same diagram, reuse the existing `fileKey`. Decide whether the old attempt should remain beside the new one or be removed before regenerating. Do not create a new draft file for every wording adjustment.

## Import or redraw a local diagram

### Import an SVG when visual fidelity is the priority

1. Render the canonical source with the repository-local toolchain.
2. Import the SVG into Figma using the available Figma UI or connector workflow.
3. Keep the original DSL and SVG. Treat imported vector content as a visual baseline; it may arrive as a grouped or flattened structure and may not expose semantic nodes.
4. If individual nodes must remain independently editable, reconstruct those nodes as Figma shapes, text, and connectors or generate a structured FigJam diagram first.

An imported PNG is suitable only as a visual reference or background. It is not an editable diagram source.

### Reconstruct a structured diagram

Use this path when the user needs editable nodes, connectors, labels, or layout rules rather than a faithful snapshot:

1. Read the relevant Figma API guidance before using `use_figma`; for a FigJam board also read the FigJam-specific guidance.
2. Inspect the target file and its conventions before creating nodes. In Design files, use the metadata/inspection tools available for the file; in FigJam, use `get_figjam`.
3. Create the diagram in small batches: containers and nodes first, then text, then connectors and labels.
4. Return every created or mutated node ID after each write. Keep those IDs for later validation and cleanup.
5. Match existing names, colors, typography, and grouping conventions unless the user asks for a new visual treatment.

Do not recreate an entire existing board when a focused mutation can preserve its comments, links, and unrelated diagrams.

## Reusable example: Mermaid BFS to FigJam

When a local Mermaid source such as `examples/ai-algorithms/sources/mermaid-bfs.mmd` should become an editable FigJam teaching diagram:

1. Keep `mermaid-bfs.mmd` as the canonical source and render `mermaid-bfs.png` or `mermaid-bfs.svg` locally for comparison.
2. Convert the source into a supported flowchart Mermaid input with stable IDs such as `start`, `queue`, `visit`, and `done`.
3. Load `figma-generate-diagram`, call `generate_diagram` with a descriptive name such as `Breadth-first search`, and record the returned board URL.
4. If the user asks for highlighted layers or explanatory stickies, load `figma-use` and `figma-use-figjam`, inspect the board, and add those annotations in a separate section.
5. Deliver the board link together with the `.mmd` source, the local rendered output, and the exact render command. The board link alone is not a reproducible replacement for the source.

## Edit an existing Figma or FigJam diagram

Inspect before editing. Confirm the URL type first:

- `figma.com/design/...` is a Design file. Use the Design-file inspection and `use_figma` workflows.
- `figma.com/board/...` is a FigJam file. Use `get_figjam` for the node tree and FigJam-supported APIs for edits.

Then:

1. Identify the target page/section and node IDs from inspection output.
2. State the intended mutation in terms of nodes and relationships: move, rename, recolor, add, delete, or reconnect.
3. Apply the smallest useful edit. For text changes, load the node's current font before mutating it. For multi-page Design files, switch to one page per call and keep calls independent.
4. Return affected IDs and inspect the resulting structure.
5. Capture a screenshot of the changed region or board and compare it with the local rendered baseline.

If an imported SVG is one opaque group, do not promise semantic node edits. Either edit the vector group as a whole or reconstruct the required portion as native Figma/FigJam nodes.

## Hybrid annotations and styling

Use a hybrid workflow when the base diagram is correct but needs presentation or review context:

1. Generate or import the base diagram.
2. Add sections, legends, stickies, callouts, or highlighted paths in a separate, named layer or section.
3. Keep semantic diagram nodes distinguishable from review annotations so later regeneration does not silently overwrite them.
4. Verify that annotations do not obscure connectors or change the meaning of arrows and boundaries.

For generated FigJam boards, use FigJam-only node types and APIs. Do not call Design-only APIs such as `figma.createPage()` in a FigJam file.

## Verification and delivery

Run both sides of the workflow:

- **Local:** validate the canonical source and rerender the expected SVG/PNG/PDF with the pinned toolchain. Check that document links and manifest paths exist.
- **Figma/FigJam:** verify the returned URL, inspect the expected node/section structure, confirm node IDs for edits, and take a screenshot for visual review.

Check for missing nodes, incorrect arrow direction, clipping, overlap, unreadable text, inconsistent fonts, and annotations covering content. Report when a visual check could not be performed.

The final delivery should list:

- canonical source and local rendered outputs;
- Figma/FigJam URL and whether it was created, imported, or edited;
- any node IDs or sections that were changed when relevant;
- the exact local render/validation commands;
- unresolved assumptions, such as a screenshot-only reconstruction or an imported SVG that remains grouped.
