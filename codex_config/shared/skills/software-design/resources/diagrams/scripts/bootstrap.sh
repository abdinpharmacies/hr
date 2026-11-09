#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bin="$root/tools/bin"
plantuml_version="1.2026.8"
structurizr_version="2025.11.09"
mkdir -p "$bin"
(cd "$root" && npm rebuild drawio-headless --foreground-scripts)

if [[ ! -f "$bin/plantuml.jar" ]]; then
  curl -fL "https://github.com/plantuml/plantuml/releases/download/v${plantuml_version}/plantuml-${plantuml_version}.jar" -o "$bin/plantuml.jar"
fi
if [[ ! -x "$bin/structurizr/structurizr.sh" ]]; then
  tmp="$(mktemp)"
  curl -fL "https://github.com/structurizr/cli/releases/download/v${structurizr_version}/structurizr-cli.zip" -o "$tmp"
  mkdir -p "$bin/structurizr"
  unzip -oq "$tmp" -d "$bin/structurizr"
  chmod +x "$bin/structurizr/structurizr.sh"
  rm -f "$tmp"
fi
echo "Java tools installed under $bin"
