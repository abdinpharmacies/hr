$script:AiWorkflowOpenCodeRoot = Split-Path -Parent $PSScriptRoot

# OpenCode reads OPENCODE_CONFIG_DIR when a server starts. The shared background
# service is started once without a profile, so profile launches need a private
# server (--standalone) or they would silently reuse the global configuration.
$script:AiWorkflowOpenCodeProfileCommands = @('run', 'api', 'mini')
$script:AiWorkflowOpenCodeServiceCommands = @(
    'upgrade', 'update', 'uninstall', 'acp', 'debug', 'auth', 'mcp', 'plugin',
    'models', 'stats', 'session', 'service', 'reload', 'pair', 'serve'
)

function Invoke-AiWorkflowOpenCode {
    param([string]$ProfileName, [object[]]$ToolArguments)
    $previous = [Environment]::GetEnvironmentVariable('OPENCODE_CONFIG_DIR', 'Process')
    try {
        $env:OPENCODE_CONFIG_DIR = Join-Path $script:AiWorkflowOpenCodeRoot "profiles/$ProfileName"
        $arguments = @($ToolArguments)
        $command = if ($arguments.Count -gt 0) { [string]$arguments[0] } else { '' }
        if ($script:AiWorkflowOpenCodeProfileCommands -contains $command) {
            $arguments = @($command, '--standalone') + @($arguments | Select-Object -Skip 1)
        }
        elseif ($script:AiWorkflowOpenCodeServiceCommands -notcontains $command) {
            # Root TUI invocation, a directory argument, or a root flag.
            $arguments = @('--standalone') + $arguments
        }
        & opencode @arguments
    }
    finally {
        [Environment]::SetEnvironmentVariable('OPENCODE_CONFIG_DIR', $previous, 'Process')
    }
}

function opencode-flutter { Invoke-AiWorkflowOpenCode -ProfileName flutter -ToolArguments $args }
function opencode-jaspr { Invoke-AiWorkflowOpenCode -ProfileName jaspr -ToolArguments $args }
function opencode-react { Invoke-AiWorkflowOpenCode -ProfileName react -ToolArguments $args }
function opencode-node { Invoke-AiWorkflowOpenCode -ProfileName node -ToolArguments $args }
function opencode-python { Invoke-AiWorkflowOpenCode -ProfileName python -ToolArguments $args }
function opencode-odoo { Invoke-AiWorkflowOpenCode -ProfileName python -ToolArguments $args }
