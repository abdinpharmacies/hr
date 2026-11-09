$ErrorActionPreference = 'Stop'

[Console]::OutputEncoding = [Text.UTF8Encoding]::new()
$OutputEncoding = [Console]::OutputEncoding
$env:PYTHONIOENCODING = 'utf-8'

function Require-Command([string]$Name, [string]$Hint) {
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "$Name is required but was not found. $Hint"
  }
}

Require-Command 'node' 'Install Node.js 20+ and restart PowerShell.'
Require-Command 'npm' 'Install npm with Node.js 20+.'
Require-Command 'java' 'Install Java 17+ and ensure java is on PATH.'
Require-Command 'pwsh' 'Run this script from PowerShell 7+.'

$nodeMajor = [int]((node --version).TrimStart('v').Split('.')[0])
$javaVersion = (java -version 2>&1 | Select-Object -First 1)
if ($nodeMajor -lt 20) { throw "Node.js 20+ is required; found $(node --version)." }
$javaMatch = [regex]::Match($javaVersion, '"(?<version>[^" ]+)"')
if (-not $javaMatch.Success) { throw "Could not determine Java version from: $javaVersion" }
$javaMajorText = $javaMatch.Groups['version'].Value.Split('.')[0]
$javaMajor = [int]$javaMajorText
if ($javaMajor -eq 1) { $javaMajor = [int]$javaMatch.Groups['version'].Value.Split('.')[1] }
if ($javaMajor -lt 17) { throw "Java 17+ is required; found $javaVersion" }
Write-Host "Using Node.js $(node --version) and $javaVersion"

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$bin = Join-Path $root 'tools/bin'
$plantumlVersion = '1.2026.8'
$structurizrVersion = '2025.11.09'
$plantuml = Join-Path $bin 'plantuml.jar'
$structurizrDir = Join-Path $bin 'structurizr'
$structurizrZip = Join-Path $bin 'structurizr-cli.zip'

New-Item -ItemType Directory -Force $bin | Out-Null
Push-Location $root
try { npm rebuild drawio-headless --foreground-scripts }
finally { Pop-Location }
if (-not (Test-Path $plantuml)) {
  Invoke-WebRequest "https://github.com/plantuml/plantuml/releases/download/v$plantumlVersion/plantuml-$plantumlVersion.jar" -OutFile $plantuml
}
if (-not (Test-Path (Join-Path $structurizrDir 'structurizr.bat'))) {
  Invoke-WebRequest "https://github.com/structurizr/cli/releases/download/v$structurizrVersion/structurizr-cli.zip" -OutFile $structurizrZip
  Expand-Archive -Force $structurizrZip $structurizrDir
}
Write-Host "Java tools installed under $bin"
