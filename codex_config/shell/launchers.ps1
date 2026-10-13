$script:AiWorkflowCodexLauncher = Join-Path $PSScriptRoot '../scripts/launch.py'
function codex { & python -B $script:AiWorkflowCodexLauncher @args }
function codex-flutter { codex --profile flutter @args }
function codex-jaspr { codex --profile jaspr @args }
function codex-react { codex --profile react @args }
function codex-node { codex --profile node @args }
function codex-odoo { codex --profile odoo @args }
