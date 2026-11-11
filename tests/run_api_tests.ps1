# HTTP-API-Tests des Pico W: Smoke-Tests und OpenAPI mit Schemathesis
# Start aus dem Repository: .\tests\run_api_tests.ps1 -PicoIP 192.168.0.79
# Optional nur Smoke und Examples: -SkipCoverage
# Optional zusaetzlich Fuzzing: -IncludeFuzzing

param(
    [string]$PicoIP = "192.168.0.79",
    [switch]$SkipCoverage,
    [switch]$IncludeFuzzing
)

$RepoPath = Split-Path -Parent $PSScriptRoot
$OpenAPI = Join-Path $RepoPath "docs\iot-specs\openapi.yaml"
$SmokeTest = Join-Path $PSScriptRoot "smoke_api.py"
$BaseURL = "http://$PicoIP"

if (-not (Test-Path $OpenAPI)) { Write-Error "openapi.yaml nicht gefunden: $OpenAPI"; exit 1 }
if (-not (Test-Path $SmokeTest)) { Write-Error "smoke_api.py nicht gefunden: $SmokeTest"; exit 1 }
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python wurde nicht gefunden. Bitte Python 3 installieren."; exit 1
}
if (-not (Get-Command schemathesis -ErrorAction SilentlyContinue)) {
    Write-Error "Schemathesis nicht gefunden. Installation: python -m pip install -r tests/requirements.txt"; exit 1
}

$OriginalInterval = $null
$TestFailed = $false
$RestoreFailed = $false

Push-Location $RepoPath
try {
    Write-Host "`n[0] Sichere urspruengliches Intervall..." -ForegroundColor Cyan
    $output = & python $SmokeTest --url $BaseURL --get-interval
    if ($LASTEXITCODE -ne 0) { throw "GET /config nicht erreichbar oder ungueltig." }
    $OriginalInterval = [int]($output | Select-Object -Last 1)
    Write-Host "Gesichertes Intervall: $OriginalInterval Sekunden" -ForegroundColor Green

    Write-Host "`n[1] Python-Smoke-Tests..." -ForegroundColor Cyan
    & python $SmokeTest --url $BaseURL
    if ($LASTEXITCODE -ne 0) { throw "Smoke-Tests fehlgeschlagen." }

    Write-Host "`n[2] Schemathesis Examples..." -ForegroundColor Cyan
    & schemathesis run $OpenAPI --url $BaseURL --workers 1 `
        --phases examples --request-timeout 10 --max-failures 3
    if ($LASTEXITCODE -ne 0) { throw "Schemathesis Examples fehlgeschlagen." }

    if (-not $SkipCoverage) {
        Write-Host "`n[3] Schemathesis Coverage..." -ForegroundColor Cyan
        & schemathesis run $OpenAPI --url $BaseURL --workers 1 `
            --phases coverage --request-timeout 10 --max-failures 3
        if ($LASTEXITCODE -ne 0) { throw "Schemathesis Coverage fehlgeschlagen." }
    } else {
        Write-Host "`n[3] Coverage uebersprungen." -ForegroundColor Yellow
    }

    if ($IncludeFuzzing) {
        Write-Host "`n[4] Schemathesis Fuzzing (optional)..." -ForegroundColor Cyan
        & schemathesis run $OpenAPI --url $BaseURL --workers 1 `
            --phases fuzzing --max-examples 20 --generation-deterministic `
            --request-timeout 10 --max-failures 3
        if ($LASTEXITCODE -ne 0) { throw "Schemathesis Fuzzing fehlgeschlagen." }
    }
} catch {
    $TestFailed = $true
    Write-Host "`nTEST FEHLGESCHLAGEN: $_" -ForegroundColor Red
} finally {
    # Gilt auch bei fehlgeschlagenen Schemathesis-Tests.
    if ($null -ne $OriginalInterval) {
        Write-Host "`n[RESTORE] Urspruengliches Intervall setzen..." -ForegroundColor Cyan
        & python $SmokeTest --url $BaseURL --set-interval $OriginalInterval
        if ($LASTEXITCODE -ne 0) {
            $RestoreFailed = $true
            Write-Host "RESTORE FEHLGESCHLAGEN! Pico-Konfiguration bitte manuell pruefen." -ForegroundColor Red
        }
    }
    Pop-Location
}

if ($TestFailed -or $RestoreFailed) { exit 1 }
Write-Host "`nAlle ausgefuehrten Tests erfolgreich. Intervall wiederhergestellt." -ForegroundColor Green
exit 0
