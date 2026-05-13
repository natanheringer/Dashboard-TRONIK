
# =============================================================================
#  TRONIK Prospeccao — full SOTA pipeline
#  Executa todos os passos na ordem correta, paralelizando onde possivel.
#
#  USO:
#    .\run_pipeline.ps1                      # com Casa dos Dados API key
#    .\run_pipeline.ps1 -SkipFetch           # pula fetch-targeted (sem API key)
#    .\run_pipeline.ps1 -Tiers "t1,t2"       # so tiers proximos da sede
# =============================================================================

param(
    [string]$Tiers = "all",
    [switch]$SkipFetch,
    [switch]$SkipCnefe,
    [switch]$SkipNormalize
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$logDir = Join-Path $root "data\raw\prospeccao\_reports"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }

function Run-Step {
    param([string]$Name, [string]$Cmd, [string]$LogFile)

    Write-Host "  [$Name] Iniciando..." -ForegroundColor DarkGray
    $sw = [System.Diagnostics.Stopwatch]::StartNew()

    # Run and capture both stdout+stderr to log, without $ErrorActionPreference breaking on stderr
    $output = cmd /c "$Cmd 2>&1"
    $exitCode = $LASTEXITCODE
    $sw.Stop()

    $output | Out-File -FilePath $LogFile -Encoding utf8

    if ($exitCode -ne 0) {
        Write-Host "  [$Name] FALHOU (exit $exitCode, $([math]::Round($sw.Elapsed.TotalSeconds))s) -> $LogFile" -ForegroundColor Red
        return $false
    } else {
        Write-Host "  [$Name] OK ($([math]::Round($sw.Elapsed.TotalSeconds))s)" -ForegroundColor Green
        return $true
    }
}

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  TRONIK Pipeline  |  $timestamp" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ---------------------------------------------------------------------------
# FASE 1: Downloads (harvest sempre; fetch-targeted e cnefe se habilitados)
# ---------------------------------------------------------------------------

Write-Host "[FASE 1/3] Downloads" -ForegroundColor Yellow

$harvestLog = Join-Path $logDir "pipeline_harvest.log"
Run-Step "harvest" "python -m jobs.prospeccao harvest --steps `"ibge,geoportal,ckan_meta,pncp`"" $harvestLog

if (-not $SkipFetch) {
    if (-not $env:TRONIK_CASADOSDADOS_API_KEY) {
        Write-Host ""
        Write-Host "  AVISO: TRONIK_CASADOSDADOS_API_KEY nao definida." -ForegroundColor Yellow
        Write-Host "  Pegue em: https://portal.casadosdados.com.br/plataforma/api/chave" -ForegroundColor Yellow
        Write-Host "  Defina:   `$env:TRONIK_CASADOSDADOS_API_KEY = 'sua-chave'" -ForegroundColor Yellow
        Write-Host "  Pulando fetch-targeted." -ForegroundColor Yellow
        Write-Host ""
    } else {
        $fetchLog = Join-Path $logDir "pipeline_fetch_targeted.log"
        Run-Step "fetch-targeted" "python -m jobs.prospeccao fetch-targeted --tiers `"$Tiers`"" $fetchLog
    }
}

if (-not $SkipCnefe) {
    $cnefeLog = Join-Path $logDir "pipeline_cnefe.log"
    Run-Step "cnefe" "python -m jobs.prospeccao cnefe" $cnefeLog
}

Write-Host ""

# ---------------------------------------------------------------------------
# FASE 2: Normalizacao
# ---------------------------------------------------------------------------

if (-not $SkipNormalize) {
    Write-Host "[FASE 2/3] Normalize: dedup + geocode + RA + qid" -ForegroundColor Yellow
    $normalizeLog = Join-Path $logDir "pipeline_normalize.log"
    $ok = Run-Step "normalize" "python -m jobs.prospeccao normalize" $normalizeLog
    if (-not $ok) {
        Write-Host "  Normalize falhou. Verifique o log e tente novamente." -ForegroundColor Red
        exit 1
    }
    Write-Host ""
}

# ---------------------------------------------------------------------------
# FASE 3: ML pipeline
# ---------------------------------------------------------------------------

Write-Host "[FASE 3/3] ML: build-features + train-ranker + score-candidates" -ForegroundColor Yellow
$mlLog = Join-Path $logDir "pipeline_ml.log"
$ok = Run-Step "ranker-pipeline" "python -m jobs.prospeccao ranker-pipeline" $mlLog
if (-not $ok) {
    Write-Host "  ML pipeline falhou. Verifique o log e tente novamente." -ForegroundColor Red
    exit 1
}

Write-Host ""
$totalEnd = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Pipeline completo  |  $totalEnd" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Logs em: $logDir" -ForegroundColor DarkGray
Write-Host ""
Write-Host "Proximo passo:" -ForegroundColor Green
Write-Host "  python -m jobs.prospeccao published-scores --limit 20" -ForegroundColor Green
Write-Host ""
