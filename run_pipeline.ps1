# =============================================================================
#  TRONIK Prospeccao - SOTA Pipeline v3.2
#
#  Fases:
#    1. Downloads  - harvest IBGE/CKAN/PNCP, fetch Casa dos Dados, CNEFE, Receita
#    2. Ingestao   - receita-parse, normalize (dedup + geocode + RA + qid)
#    3. Enriquece  - brasilapi-enrich, aneel, ibram
#    4. ML         - build-features v3.2, train-ranker, score-candidates
#
#  USO RAPIDO:
#    .\run_pipeline.ps1                          # pipeline completo (com checkpoint recovery)
#    .\run_pipeline.ps1 -DemoOnly               # smoke test com 3 candidatos demo
#    .\run_pipeline.ps1 -SkipFetch -SkipCnefe   # so ML com dados existentes
#    .\run_pipeline.ps1 -SkipFetch -SkipCnefe -SkipReceita -SkipNormalize  # so retreinar
#    .\run_pipeline.ps1 -FromStep normalize    # retomar do passo 'normalize' em diante
#    .\run_pipeline.ps1 -FromStep aneel        # retomar do passo 'aneel' em diante (paralelo)
#
#  VARIAVEIS DE AMBIENTE UTEIS:
#    $env:TRONIK_CASADOSDADOS_API_KEY = "sua-chave"
#    $env:TRONIK_ANEEL_CONSUMIDORES_URL = "https://..."
#    $env:TRONIK_IBRAM_GERADORES_URL   = "https://..."
# =============================================================================

param(
    [string]$Version         = "prospeccao-ree-v3.2",
    [string]$Tiers           = "all",
    [switch]$SkipFetch,
    [switch]$SkipCnefe,
    [switch]$SkipReceita,
    [switch]$SkipNormalize,
    [switch]$SkipBrasilApi,
    [switch]$SkipAneel,
    [switch]$SkipIbram,
    [string]$FromStep        = "",
    [switch]$DemoOnly,
    [int]$BuildLimit         = 0,
    [int]$BrasilApiBatch     = 500
)

$ErrorActionPreference = "Continue"

$root             = Split-Path -Parent $MyInvocation.MyCommand.Path
$logDir           = Join-Path $root "data\raw\prospeccao\_reports"
$checkpointPath   = Join-Path $logDir "pipeline_checkpoint.json"

if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }

$pipelineStart = Get-Date
$stepResults   = [ordered]@{}

# Lista ordenada de todos os steps (em ordem de execução)
$allSteps = @(
    "harvest",
    "fetch-targeted",
    "cnefe",
    "receita-auto",
    "receita-parse",
    "normalize",
    "brasilapi-enrich",
    "aneel",
    "ibram",
    "build-features",
    "train-ranker",
    "score-candidates"
)

# Índice do step atual para controle de skip
$currentStepIndex = 0
$shouldSkipStep   = $false

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

function Write-Banner ([string]$Text, [string]$Color = "Cyan") {
    $line = "=" * 60
    Write-Host ""
    Write-Host $line -ForegroundColor $Color
    Write-Host "  $Text" -ForegroundColor $Color
    Write-Host $line -ForegroundColor $Color
    Write-Host ""
}

function Write-Phase ([string]$Text) {
    Write-Host ""
    Write-Host "[[ $Text ]]" -ForegroundColor Yellow
    Write-Host ""
}

function Run-Step {
    param(
        [string]$Name,
        [string]$Cmd,
        [switch]$Critical,
        [switch]$WarnOnly
    )

    # Verificar se este step deve ser pulado (FromStep lógica)
    $stepIndex = $allSteps.IndexOf($Name)
    if ($stepIndex -ge 0 -and $FromStep -and -not $shouldSkipStep) {
        $fromIndex = $allSteps.IndexOf($FromStep)
        if ($stepIndex -lt $fromIndex) {
            Write-Host "  -> $Name" -NoNewline -ForegroundColor DarkGray
            Write-Host "  PULADO (FromStep=$FromStep)" -ForegroundColor DarkGray
            $stepResults[$Name] = @{ ok = $true; secs = 0; skipped = $true }
            return $true
        } elseif ($stepIndex -eq $fromIndex) {
            $shouldSkipStep = $true
        }
    }

    $logFile = Join-Path $logDir "step_$($Name -replace '[^a-z0-9]','_').log"
    Write-Host "  -> $Name" -NoNewline -ForegroundColor DarkGray
    $sw = [System.Diagnostics.Stopwatch]::StartNew()

    $output = cmd /c "$Cmd 2>&1"
    $exit   = $LASTEXITCODE
    $sw.Stop()
    $secs   = [math]::Round($sw.Elapsed.TotalSeconds)

    $output | Out-File -FilePath $logFile -Encoding utf8

    if ($exit -ne 0) {
        Write-Host ("  FALHOU ({0}s) exit={1}" -f $secs, $exit) -ForegroundColor Red
        Write-Host "     Log: $logFile" -ForegroundColor DarkGray
        $stepResults[$Name] = @{ ok = $false; secs = $secs; log = $logFile }
        if ($Critical) {
            Write-Host ""
            Write-Host "  Passo critico falhou - abortando pipeline." -ForegroundColor Red
            Write-Host ""
            Show-Summary
            exit 1
        }
        return $false
    }

    Write-Host ("  OK ({0}s)" -f $secs) -ForegroundColor Green
    $stepResults[$Name] = @{ ok = $true; secs = $secs; log = $logFile }

    # Salvar checkpoint após sucesso
    Save-Checkpoint $Name

    return $true
}

function Save-Checkpoint {
    param([string]$StepName)

    $checkpoint = @{
        last_ok_step = $StepName
        version      = $Version
        timestamp    = (Get-Date -Format 'o')
    } | ConvertTo-Json

    $checkpoint | Out-File -FilePath $checkpointPath -Encoding utf8 -Force
}

function Load-Checkpoint {
    if (Test-Path $checkpointPath) {
        try {
            $data = Get-Content $checkpointPath -Raw | ConvertFrom-Json
            return $data
        } catch {
            return $null
        }
    }
    return $null
}

function Run-ParallelSteps {
    param(
        [hashtable[]]$StepDefinitions
    )

    <#
    .SYNOPSIS
        Executa múltiplos steps em paralelo via Start-Job
    .PARAMETER StepDefinitions
        Array de hashtables com chaves: Name, Cmd, Critical, WarnOnly
    #>

    $jobs = @()

    # Iniciar todos os jobs
    foreach ($stepDef in $StepDefinitions) {
        $name = $stepDef.Name
        $cmd  = $stepDef.Cmd

        Write-Host "  -> $name" -NoNewline -ForegroundColor DarkGray
        Write-Host "  INICIADO (paralelo)" -ForegroundColor Cyan

        $job = Start-Job -ScriptBlock {
            param($logDir, $name, $cmd)

            $logFile = Join-Path $logDir "step_$($name -replace '[^a-z0-9]','_').log"
            $sw = [System.Diagnostics.Stopwatch]::StartNew()

            $output = cmd /c "$cmd 2>&1"
            $exit   = $LASTEXITCODE
            $sw.Stop()
            $secs   = [math]::Round($sw.Elapsed.TotalSeconds)

            $output | Out-File -FilePath $logFile -Encoding utf8

            @{
                Name     = $name
                Exit     = $exit
                Secs     = $secs
                LogFile  = $logFile
                Output   = $output
                Critical = $stepDef.Critical
            }
        } -ArgumentList @($logDir, $name, $cmd)

        $jobs += $job
    }

    Write-Host ""

    # Aguardar todos os jobs
    $allResults = @()
    foreach ($job in $jobs) {
        $result = Receive-Job -Job $job -Wait
        $allResults += $result
        Remove-Job -Job $job
    }

    # Processar resultados
    $hasFailure = $false
    $hasCriticalFailure = $false

    foreach ($result in $allResults) {
        $name = $result.Name
        $exit = $result.Exit
        $secs = $result.Secs
        $logFile = $result.LogFile
        $isCritical = $result.Critical

        if ($exit -ne 0) {
            Write-Host ("  FALHOU {0} ({1}s) exit={2}" -f $name, $secs, $exit) -ForegroundColor Red
            Write-Host ("     Log: {0}" -f $logFile) -ForegroundColor DarkGray
            $stepResults[$name] = @{ ok = $false; secs = $secs; log = $logFile }
            $hasFailure = $true
            if ($isCritical) { $hasCriticalFailure = $true }
        } else {
            Write-Host ("  OK {0} ({1}s)" -f $name, $secs) -ForegroundColor Green
            $stepResults[$name] = @{ ok = $true; secs = $secs; log = $logFile }
            # Salvar checkpoint para cada step bem-sucedido
            Save-Checkpoint $name
        }
    }

    if ($hasCriticalFailure) {
        Write-Host ""
        Write-Host "  Passo critico falhou em paralelo - abortando pipeline." -ForegroundColor Red
        Write-Host ""
        Show-Summary
        exit 1
    }

    return -not $hasFailure
}

function Show-Summary {
    $elapsed = [math]::Round(((Get-Date) - $pipelineStart).TotalSeconds)
    $ts = Get-Date -Format 'HH:mm:ss'
    Write-Banner ("Resumo do Pipeline  |  {0}  |  {1}s total" -f $ts, $elapsed) "Cyan"
    foreach ($name in $stepResults.Keys) {
        $r = $stepResults[$name]
        if ($r.skipped) {
            Write-Host ("  [SKIP] {0}" -f $name) -ForegroundColor DarkGray
        } elseif ($r.ok) {
            Write-Host ("  [OK]  {0} ({1}s)" -f $name, $r.secs) -ForegroundColor Green
        } else {
            Write-Host ("  [ERR] {0} ({1}s)  -> {2}" -f $name, $r.secs, $r.log) -ForegroundColor Red
        }
    }
    Write-Host ""
    Write-Host "  Logs em: $logDir" -ForegroundColor DarkGray
    Write-Host "  Checkpoint: $checkpointPath" -ForegroundColor DarkGray
    Write-Host ""
}

# ---------------------------------------------------------------------------
# Header + Checkpoint Recovery
# ---------------------------------------------------------------------------

Write-Banner "TRONIK Pipeline  |  Schema $Version  |  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"

# Se não foi passado -FromStep e existe checkpoint, oferecer retomada
if (-not $FromStep) {
    $lastCheckpoint = Load-Checkpoint
    if ($lastCheckpoint) {
        Write-Host "  [CHECKPOINT] Encontrado checkpoint: last_ok_step = '$($lastCheckpoint.last_ok_step)'" -ForegroundColor Yellow
        Write-Host "               Timestamp: $($lastCheckpoint.timestamp)" -ForegroundColor DarkGray

        $options = @("&Continuar do checkpoint", "&Rodar pipeline completo", "&Cancelar")
        $choice = $host.UI.PromptForChoice(
            "Retomar pipeline?",
            "Deseja retomar do passo '$($lastCheckpoint.last_ok_step)' ou rodar tudo de novo?",
            $options,
            0
        )

        switch ($choice) {
            0 {
                Write-Host "  Retomando do step: $($lastCheckpoint.last_ok_step)" -ForegroundColor Green
                $FromStep = $lastCheckpoint.last_ok_step
            }
            1 {
                Write-Host "  Iniciando pipeline do zero." -ForegroundColor Cyan
            }
            2 {
                Write-Host "  Pipeline cancelado pelo usuário." -ForegroundColor Yellow
                exit 0
            }
        }
    }
}

if ($DemoOnly) {
    Write-Host "  [MODO DEMO] Smoke test com candidatos demo, limite=100" -ForegroundColor Magenta
    $BuildLimit  = 100
    $SkipFetch   = $true
    $SkipCnefe   = $true
    $SkipReceita = $true
    $SkipAneel   = $true
    $SkipIbram   = $true
}

if ($FromStep) {
    Write-Host "  [FromStep] Iniciando do step: $FromStep" -ForegroundColor Cyan
}

# ---------------------------------------------------------------------------
# FASE 1 - Downloads
# ---------------------------------------------------------------------------

Write-Phase "FASE 1/4 - Downloads"

Run-Step "harvest" "python -m jobs.prospeccao harvest --steps ibge,geoportal,ckan_meta,pncp"

if (-not $SkipFetch) {
    if (-not $env:TRONIK_CASADOSDADOS_API_KEY) {
        Write-Host "  [AVISO] TRONIK_CASADOSDADOS_API_KEY nao definida - pulando fetch-targeted." -ForegroundColor Yellow
        Write-Host '          Defina: $env:TRONIK_CASADOSDADOS_API_KEY = ''sua-chave''' -ForegroundColor DarkGray
    } else {
        Run-Step "fetch-targeted" "python -m jobs.prospeccao fetch-targeted --tiers $Tiers"
    }
}

if (-not $SkipCnefe) {
    Run-Step "cnefe" "python -m jobs.prospeccao cnefe"
}

if (-not $SkipReceita) {
    Run-Step "receita-auto" "python -m jobs.prospeccao receita-auto --tipo estabelecimentos --max 2"
}

# ---------------------------------------------------------------------------
# FASE 2 - Ingestao e Normalizacao
# ---------------------------------------------------------------------------

Write-Phase "FASE 2/4 - Ingestao e Normalizacao"

if (-not $SkipReceita) {
    Run-Step "receita-parse" "python -m jobs.prospeccao receita-parse" -Critical
}

if (-not $SkipNormalize) {
    Run-Step "normalize" "python -m jobs.prospeccao normalize" -Critical
}

# ---------------------------------------------------------------------------
# FASE 3 - Enriquecimento (paralelo: BrasilAPI, ANEEL, IBRAM)
# ---------------------------------------------------------------------------

Write-Phase "FASE 3/4 - Enriquecimento de Dados (paralelo)"

# Preparar steps paralelos
$parallelSteps = @()

if (-not $SkipBrasilApi) {
    $parallelSteps += @{
        Name     = "brasilapi-enrich"
        Cmd      = "python -m jobs.prospeccao brasilapi-enrich --batch $BrasilApiBatch"
        Critical = $false
        WarnOnly = $false
    }
}

if (-not $SkipAneel) {
    if (-not $env:TRONIK_ANEEL_CONSUMIDORES_URL) {
        Write-Host "  [INFO] TRONIK_ANEEL_CONSUMIDORES_URL nao definida - ANEEL vai tentar descoberta via CKAN." -ForegroundColor DarkGray
    }
    $parallelSteps += @{
        Name     = "aneel"
        Cmd      = "python -m jobs.prospeccao aneel --ufs DF,GO"
        Critical = $false
        WarnOnly = $false
    }
}

if (-not $SkipIbram) {
    if (-not $env:TRONIK_IBRAM_GERADORES_URL) {
        Write-Host "  [INFO] TRONIK_IBRAM_GERADORES_URL nao definida - IBRAM tentara CKAN DF." -ForegroundColor DarkGray
        Write-Host '         Para CSV manual: $env:TRONIK_IBRAM_GERADORES_URL = ''caminho\arquivo.csv''' -ForegroundColor DarkGray
    }
    $parallelSteps += @{
        Name     = "ibram"
        Cmd      = "python -m jobs.prospeccao ibram"
        Critical = $false
        WarnOnly = $false
    }
}

# Executar todos em paralelo se houver steps
if ($parallelSteps.Count -gt 0) {
    Write-Host "  Iniciando $($parallelSteps.Count) jobs em paralelo..." -ForegroundColor Yellow
    Write-Host ""
    Run-ParallelSteps $parallelSteps
    Write-Host ""
}

# ---------------------------------------------------------------------------
# FASE 4 - ML Pipeline
# ---------------------------------------------------------------------------

Write-Phase "FASE 4/4 - ML: build-features + train + score"

$buildCmd = "python -m jobs.prospeccao build-features --version $Version"
if ($DemoOnly)         { $buildCmd += " --seed-demo" }
if ($BuildLimit -gt 0) { $buildCmd += " --limit $BuildLimit" }
Run-Step "build-features" $buildCmd -Critical

Run-Step "train-ranker" "python -m jobs.prospeccao train-ranker --pipeline-version $Version" -Critical

Run-Step "score-candidates" "python -m jobs.prospeccao score-candidates"

# ---------------------------------------------------------------------------
# Resultado final
# ---------------------------------------------------------------------------

Show-Summary

$errors = ($stepResults.Values | Where-Object { -not $_.ok }).Count
if ($errors -eq 0) {
    Write-Host "  Pipeline completo sem erros!" -ForegroundColor Green
} else {
    Write-Host "  $errors passo(s) com erro - verifique os logs acima." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "  Top 20 candidatos:" -ForegroundColor Cyan
Write-Host "    python -m jobs.prospeccao published-scores --limit 20" -ForegroundColor White
Write-Host ""
Write-Host "  Alta prioridade:" -ForegroundColor Cyan
Write-Host "    python -m jobs.prospeccao published-scores --prioridade alta --limit 50" -ForegroundColor White
Write-Host ""
