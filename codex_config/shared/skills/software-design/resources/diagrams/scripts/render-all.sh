#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
demo="$root/examples/shop"
source_dir="$demo/sources"
rendered="$demo/rendered"
bin="$root/tools/bin"
mkdir -p "$rendered"
test -f "$bin/plantuml.jar" || { echo "PlantUML is missing. Run scripts/bootstrap.sh." >&2; exit 1; }
test -x "$bin/structurizr/structurizr.sh" || { echo "Structurizr CLI is missing. Run scripts/bootstrap.sh." >&2; exit 1; }
find "$root/node_modules/drawio-headless/vendor" -type f -maxdepth 1 | grep -q . || { echo "drawio-headless binary is missing. Run scripts/bootstrap.sh after npm ci." >&2; exit 1; }

npm exec -- mmdc -p "$root/scripts/puppeteer-ci.json" -i "$source_dir/mermaid-sequence.mmd" -o "$rendered/mermaid-sequence.svg"
npm exec -- mmdc -p "$root/scripts/puppeteer-ci.json" -i "$source_dir/mermaid-state.mmd" -o "$rendered/mermaid-state.png" -b transparent
java -jar "$bin/plantuml.jar" -tsvg -Playout=smetana "$source_dir/plantuml-class.puml" "$source_dir/plantuml-deployment.puml"
mv "$source_dir/plantuml-class.svg" "$rendered/plantuml-class.svg"
mv "$source_dir/plantuml-deployment.svg" "$rendered/plantuml-deployment.svg"
"$bin/structurizr/structurizr.sh" validate -w "$source_dir/structurizr-shop.dsl"
"$bin/structurizr/structurizr.sh" export -w "$source_dir/structurizr-shop.dsl" -f plantuml -o "$rendered"
java -jar "$bin/plantuml.jar" -tsvg -Playout=smetana "$rendered/structurizr-context.puml" "$rendered/structurizr-containers.puml"
node "$root/scripts/render-wasm.mjs"
npm exec -- drawio-headless render "$source_dir/drawio-architecture.drawio" "$rendered/drawio-architecture.svg"
npm exec -- drawio-headless render --format png "$source_dir/drawio-checkout.drawio" "$rendered/drawio-checkout.png"
for output in \
  mermaid-sequence.svg mermaid-state.png plantuml-class.svg plantuml-deployment.svg \
  structurizr-context.svg structurizr-containers.svg d2-architecture.svg d2-checkout.svg \
  graphviz-dependencies.svg graphviz-states.svg drawio-architecture.svg drawio-checkout.png; do
  test -s "$rendered/$output" || { echo "Expected output was not created: $rendered/$output" >&2; exit 1; }
done
echo "Rendered diagrams in $rendered"
