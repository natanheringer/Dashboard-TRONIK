# Gera SVG (e opcionalmente PNG) a partir de docs/diagramas/*.mmd
# Uso: .\scripts\render_diagramas.ps1
#      .\scripts\render_diagramas.ps1 -Png

param([switch]$Png)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
$srcDir = Join-Path $root "docs\diagramas"
$svgDir = Join-Path $srcDir "svg"
$pngDir = Join-Path $srcDir "png"

New-Item -ItemType Directory -Force -Path $svgDir | Out-Null
if ($Png) { New-Item -ItemType Directory -Force -Path $pngDir | Out-Null }

$mmdc = "npx"
$mmdcArgs = @("--yes", "@mermaid-js/mermaid-cli@11.4.0")

Get-ChildItem (Join-Path $srcDir "*.mmd") | ForEach-Object {
    $base = $_.BaseName
    $svgOut = Join-Path $svgDir "$base.svg"
    Write-Host "SVG $base ..."
    & $mmdc @mmdcArgs -i $_.FullName -o $svgOut -b transparent
    if ($LASTEXITCODE -ne 0) { throw "Falha ao renderizar $($_.Name)" }
    if ($Png) {
        $pngOut = Join-Path $pngDir "$base.png"
        Write-Host "PNG $base ..."
        & $mmdc @mmdcArgs -i $_.FullName -o $pngOut -b transparent
        if ($LASTEXITCODE -ne 0) { throw "Falha PNG $($_.Name)" }
    }
}

Write-Host "Concluido: $svgDir"
