# Rendered architecture images

Use the retained references according to the requested flow, with distinct roles:

- [Complete-system reference](../assets/complete-system-reference.png): the default visual theme and the categories to consider for whole-system coverage. Open it before styling an image.
- [Arrow reference](../assets/architecture-style-reference.png): the connected flow structure, arrow directions and concise edge labels. Open it before laying out connections.
- [Accepted usage-flow example](../assets/usage-flow-reference.png): actor entry paths, concise actions under each stage, and connected fulfillment, prescription and data-source paths. Open it for a requested usage-flow image. It is not an accepted system-flow layout.

These are user-supplied or user-approved visual examples, not evidence of deployed technology. Follow a different explicit user style when provided. For a whole-system image read [Whole-system coverage](system-coverage.md); for a feature image stay within that feature.

## Visual treatment

- White background, bold dark headings with restrained purple accents, spacious rounded group frames and light tinted card backgrounds, following the complete-system reference.
- Use consistent role colors inspired by the reference: teal ingress, purple backend, red/pink auth, green database, orange cache/queue, blue runtime/cloud, pink delivery automation and green monitoring. Label roles as well as coloring them.
- Use small recognizable icons with readable actual component names. Show the selected technology only, not every alternative logo from the reference. Use generic symbols when the technology is unknown; do not copy the reference's brand watermark or title.
- Arrange components by the real flow rather than copying the reference's disconnected columns. Use clear directional arrows and short action/protocol labels like the arrow reference. Keep arrowheads visible outside cards, route around labels, and avoid ambiguous crossings.
- Distinguish normal calls, asynchronous events, and operational/deployment links by labels and a small legend. Use red for actual failure paths and dashed connectors for explicitly explained semantics; do not communicate meaning through color alone.
- Modest card/icon shadows are acceptable when they aid hierarchy. Avoid decorative backgrounds and excessive effects that reduce readability.

Match this visual language rather than copying the sample's layout when the real graph needs a different arrangement. Keep technical text editable and precise. Use deterministic SVG or an installed Mermaid, Graphviz, D2, PlantUML or draw.io renderer. Directly authored SVG is acceptable as the canonical vector source for a small diagram; rasterize a preview with an available tool for inspection. Do not require AI image generation for engineering diagrams.

## Delivery and verification

Retain one canonical source plus the generated SVG/PNG. For a directly authored SVG, the SVG itself is the source; do not create a duplicate DSL just for compliance. Present the actual image in chat where supported and provide the artifact link. A diagram code block or a screenshot of source text does not satisfy image delivery.

Check the source model and inspect the rendered image at normal reading size: arrows reach the intended nodes, labels do not overlap connectors, nothing is clipped, icons do not obscure names, and Arabic text has correct shaping/direction. If both text and image views are requested, compare their nodes, edge direction and status labels.

Document-template tooling is independent of standalone diagram rendering. If a DOCX template runtime is unavailable, continue producing the requested standalone text/image views with available tools and report the document-specific blocker. If no renderer or preview tool is available, provide the editable source and text view, explicitly mark the image unrendered/unverified, and do not claim successful image delivery. Do not install dependencies without authorization.
