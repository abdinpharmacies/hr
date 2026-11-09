# Diagram delivery

Choose the view from the question: component for responsibilities, sequence for ordered interactions, state for transitions, data flow for transformations, deployment for infrastructure, C4 context/container for system scope. Do not require all C4 levels or class diagrams for every task.

Choose the flow's subject before drawing:

- For a usage flow, read [Usage flow](flows/usage.md). Show who acts at each stage, what they do, and what they can see next. The accepted eCommerce example is this kind of view.
- For a system flow, read [System flow](flows/system.md). Show actual components, communication, data and state changes. Do not reuse an actor journey as the technical graph.
- If both are requested, create separately labeled views whose shared facts agree. Use the user's established meaning in an ongoing conversation; do not silently switch types because both contain arrows.

## Choose the delivery mode

For a general request to draw, show or explain a software design, default to a compact plain-character text diagram only. Generate PNG/SVG only when the user explicitly requests an image or that format. Do not load image-rendering guidance or run a renderer for the default text path. Honor other explicit format requests, including Mermaid, and preserve the format when editing an existing artifact.

- For plain characters such as `/`, `|`, `-`, `+` and `>`, read [Text diagrams](text-diagrams.md). This path requires no renderer or package installation.
- For an actual diagram image in the user's reference style, read [Architecture images](architecture-images.md). This path delivers SVG/PNG, not merely Mermaid code.
- Only when both are requested, establish one set of nodes and labeled edges first, then create consistent text and image views. The text view can simplify the image but must not contradict it.

Mermaid remains available for explicitly requested Markdown diagrams and as an editable source for rendering. Use Structurizr when several C4 views need one shared model; PlantUML for complex sequences/UML, Graphviz for dependency networks, and draw.io for manual diagram editing. Read only the relevant format section in [renderer guide](../resources/diagrams/GUIDE.md) if commands or advanced export are needed. In that guide, skillRoot means `resources/diagrams`, not this skill's root. For Figma/FigJam specifically, read its [workflow](../resources/diagrams/references/figma-workflow.md); an available connector and user-requested remote delivery are required.

Choose one editable canonical source. If using the C4 analyzer, `c4-model.json` owns the model and generated Mermaid/SVG are outputs; do not maintain a second independent model. A small inline diagram can use its Markdown block as source. Images should retain their editable source beside them or in the project's established diagram directory.

For a requested picture, generate SVG or PNG, open it for visual inspection, and link/display the artifact. A DSL block alone is not image delivery. If the renderer is unavailable, report the limitation and provide the editable source; do not claim rendering or visual validation. Prefer installed project tools or the bundled locked toolchain; do not download packages without authorization. Read bootstrap scripts before executing them. Bundled gallery scripts validate only their examples, not user diagrams.

For one diagram, state purpose and output location briefly. Use the [project workflow](../resources/diagrams/references/project-workflow.md) and manifest only for multi-file/document publication or reproducible diagram bundles. User-requested file and publication scope wins; no Git operations are implied by creating artifacts.

Use stable IDs, directional edges with action labels, explicit boundaries and a legend when notation needs explanation. Separate current/proposed states and distinguish calls, data flow and ownership. Verify participants against evidence, syntax, output existence and document links; inspect images for clipping, overlap, readable text and Arabic font/shaping where used. Repair the source and rerender rather than editing generated images. Report uncompleted visual checks honestly.
