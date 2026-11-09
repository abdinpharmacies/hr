_ai_workflow_opencode_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

# OpenCode reads OPENCODE_CONFIG_DIR when a server starts. The shared background
# service is started once without a profile, so profile launches need a private
# server (--standalone) or they would silently reuse the global configuration.
_ai_workflow_opencode() {
  local profile="$1"
  shift
  local args=("$@")
  case "${args[0]:-}" in
    run | api | mini)
      args=("${args[0]}" --standalone "${args[@]:1}")
      ;;
    upgrade | update | uninstall | acp | debug | auth | mcp | plugin | models | stats | session | service | reload | pair | serve)
      ;;
    *)
      args=(--standalone "${args[@]}")
      ;;
  esac
  OPENCODE_CONFIG_DIR="$_ai_workflow_opencode_root/profiles/$profile" command opencode "${args[@]}"
}

opencode-flutter() { _ai_workflow_opencode flutter "$@"; }
opencode-jaspr() { _ai_workflow_opencode jaspr "$@"; }
opencode-react() { _ai_workflow_opencode react "$@"; }
opencode-node() { _ai_workflow_opencode node "$@"; }
opencode-python() { _ai_workflow_opencode python "$@"; }
opencode-odoo() { _ai_workflow_opencode python "$@"; }
