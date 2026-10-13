_AI_WORKFLOW_CODEX_LAUNCHER="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../scripts" && pwd)/launch.py"
codex() { python3 -B "$_AI_WORKFLOW_CODEX_LAUNCHER" "$@"; }
codex-flutter() { codex --profile flutter "$@"; }
codex-jaspr() { codex --profile jaspr "$@"; }
codex-react() { codex --profile react "$@"; }
codex-node() { codex --profile node "$@"; }
codex-odoo() { codex --profile odoo "$@"; }
