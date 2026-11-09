$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
[Console]::OutputEncoding = [Text.UTF8Encoding]::new()
$OutputEncoding = [Console]::OutputEncoding
$env:PYTHONIOENCODING = 'utf-8'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$demo = Join-Path $repoRoot 'examples/shop'
$source = Join-Path $demo 'sources'
$rendered = Join-Path $demo 'rendered'
$bin = Join-Path $repoRoot 'tools/bin'
$structurizr = Join-Path $bin 'structurizr/structurizr.bat'
$plantuml = Join-Path $bin 'plantuml.jar'
$drawio = Join-Path $repoRoot 'node_modules/drawio-headless/vendor/drawio-headless.exe'
$puppeteerConfig = Join-Path $repoRoot 'scripts/puppeteer-ci.json'

if (-not (Test-Path $plantuml)) { throw "PlantUML is missing. Run scripts/bootstrap.ps1." }
if (-not (Test-Path (Join-Path $bin 'structurizr/structurizr.bat'))) { throw "Structurizr CLI is missing. Run scripts/bootstrap.ps1." }
if (-not (Test-Path $drawio)) { throw "drawio-headless binary is missing. Run scripts/bootstrap.ps1 after npm ci." }

New-Item -ItemType Directory -Force $rendered | Out-Null

Push-Location $demo
try {
  npm exec -- mmdc -p $puppeteerConfig -i (Join-Path $source 'mermaid-sequence.mmd') -o (Join-Path $rendered 'mermaid-sequence.svg')
  npm exec -- mmdc -p $puppeteerConfig -i (Join-Path $source 'mermaid-state.mmd') -o (Join-Path $rendered 'mermaid-state.png') -b transparent

  java -jar $plantuml -tsvg -Playout=smetana (Join-Path $source 'plantuml-class.puml') (Join-Path $source 'plantuml-deployment.puml')
  Move-Item (Join-Path $source 'plantuml-class.svg') (Join-Path $rendered 'plantuml-class.svg') -Force
  Move-Item (Join-Path $source 'plantuml-deployment.svg') (Join-Path $rendered 'plantuml-deployment.svg') -Force

  & $structurizr validate -w (Join-Path $source 'structurizr-shop.dsl')
  & $structurizr export -w (Join-Path $source 'structurizr-shop.dsl') -f plantuml -o $rendered
  java -jar $plantuml -tsvg -Playout=smetana (Join-Path $rendered 'structurizr-context.puml') (Join-Path $rendered 'structurizr-containers.puml')

  Push-Location $repoRoot
  try {
    node scripts/render-wasm.mjs
    npm exec -- drawio-headless render (Join-Path $source 'drawio-architecture.drawio') (Join-Path $rendered 'drawio-architecture.svg')
  npm exec -- drawio-headless render --format png (Join-Path $source 'drawio-checkout.drawio') (Join-Path $rendered 'drawio-checkout.png')
  }
  finally { Pop-Location }
}
finally { Pop-Location }

@(
  'mermaid-sequence.svg', 'mermaid-state.png', 'plantuml-class.svg',
  'plantuml-deployment.svg', 'structurizr-context.svg',
  'structurizr-containers.svg', 'd2-architecture.svg',
  'd2-checkout.svg', 'graphviz-dependencies.svg', 'graphviz-states.svg',
  'drawio-architecture.svg', 'drawio-checkout.png'
) | ForEach-Object {
  $output = Join-Path $rendered $_
  if (-not (Test-Path $output)) { throw "Expected output was not created: $output" }
}

Write-Host "Rendered diagrams in $demo"
Write-Host 'Output manifest:'
Get-ChildItem -LiteralPath $rendered -File | Sort-Object Name | ForEach-Object {
  Write-Host ("- " + $_.FullName)
}
