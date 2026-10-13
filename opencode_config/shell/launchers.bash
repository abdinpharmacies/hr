_ai_workflow_opencode_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
opencode-flutter() { OPENCODE_CONFIG_DIR="$_ai_workflow_opencode_root/profiles/flutter" command opencode "$@"; }
opencode-jaspr() { OPENCODE_CONFIG_DIR="$_ai_workflow_opencode_root/profiles/jaspr" command opencode "$@"; }
opencode-react() { OPENCODE_CONFIG_DIR="$_ai_workflow_opencode_root/profiles/react" command opencode "$@"; }
opencode-node() { OPENCODE_CONFIG_DIR="$_ai_workflow_opencode_root/profiles/node" command opencode "$@"; }
opencode-python() { OPENCODE_CONFIG_DIR="$_ai_workflow_opencode_root/profiles/python" command opencode "$@"; }
opencode-odoo() { OPENCODE_CONFIG_DIR="$_ai_workflow_opencode_root/profiles/python" command opencode "$@"; }
