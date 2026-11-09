# AI and algorithms diagram gallery

This is the second gallery for the `software-diagrams` skill. It shows how the same local toolchain can explain AI model structure, model serving, neural-network building blocks, data structures, and algorithms.

The diagrams are educational abstractions. The DeepSeek-style MoE view is a generic mixture-of-experts inference flow; it is not a claim that every DeepSeek release has exactly this topology.

## Gallery

| Format | Diagram | Source | Rendered output |
|---|---|---|---|
| Mermaid | Transformer block data flow | [source](sources/mermaid-transformer.mmd) | [SVG](rendered/mermaid-transformer.svg) |
| Mermaid | Breadth-first search flow | [source](sources/mermaid-bfs.mmd) | [PNG](rendered/mermaid-bfs.png) |
| PlantUML | ResNet residual block | [source](sources/plantuml-resnet.puml) | [SVG](rendered/plantuml-resnet.svg) |
| Structurizr DSL | LLM serving context and containers | [source](sources/structurizr-llm-serving.dsl) | [context SVG](rendered/structurizr-context.svg) · [containers SVG](rendered/structurizr-containers.svg) |
| D2 | GPT/DeepSeek-style MoE inference | [source](sources/d2-moe-inference.d2) | [SVG](rendered/d2-moe-inference.svg) |
| Graphviz DOT | Transformer dependency graph | [source](sources/graphviz-transformer.dot) | [SVG](rendered/graphviz-transformer.svg) |
| Graphviz DOT | Binary search tree | [source](sources/graphviz-bst.dot) | [SVG](rendered/graphviz-bst.svg) |
| Graphviz DOT | Weighted graph | [source](sources/graphviz-graph.dot) | [SVG](rendered/graphviz-graph.svg) |
| Graphviz DOT | Stack | [source](sources/graphviz-stack.dot) | [SVG](rendered/graphviz-stack.svg) |
| Graphviz DOT | Queue | [source](sources/graphviz-queue.dot) | [SVG](rendered/graphviz-queue.svg) |
| Graphviz DOT | Hash table | [source](sources/graphviz-hash-table.dot) | [SVG](rendered/graphviz-hash-table.svg) |
| draw.io XML | Editable Transformer teaching view | [source](sources/drawio-transformer.drawio) | [PNG](rendered/drawio-transformer.png) |

## What this demonstrates

- Mermaid is concise for a readable pipeline and algorithm flow.
- PlantUML makes residual paths and explanatory notes easy to keep with the source.
- Structurizr keeps a high-level LLM product model consistent across context and container views.
- D2 handles a nested expert pool with a compact modern layout.
- Graphviz is useful for dependency graphs and tree-shaped data structures.
- Graphviz also makes graph, stack, queue, and hash-table layouts explicit while keeping the data structure editable as text.
- draw.io XML remains editable for teaching slides and manual layout adjustments.

## Render commands

From the repository root, after `npm ci` and `pwsh ./scripts/bootstrap.ps1`:

```powershell
pwsh ./scripts/render-ai-algorithms.ps1
```

On macOS/Linux:

```bash
bash ./scripts/render-ai-algorithms.sh
```

The scripts write generated files only to `examples/ai-algorithms/rendered/` and preserve every source file under `sources/`.
