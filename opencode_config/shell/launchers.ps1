$script:AiWorkflowOpenCodeRoot = Split-Path -Parent $PSScriptRoot

function Invoke-AiWorkflowOpenCode {
    param([string]$ProfileName, [object[]]$ToolArguments)
    $previous = [Environment]::GetEnvironmentVariable('OPENCODE_CONFIG_DIR', 'Process')
    try {
        $env:OPENCODE_CONFIG_DIR = Join-Path $script:AiWorkflowOpenCodeRoot "profiles/$ProfileName"
        & opencode @ToolArguments
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
