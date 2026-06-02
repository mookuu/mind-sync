<#:
.SYNOPSIS
    Run mind-sync tests in the local .venv.
.DESCRIPTION
    Activates .venv at the repo root, installs / updates
    dependencies as needed, and runs pytest with any
    extra arguments passed through.
.PARAMETER Filter
    Optional pytest test filter expression, e.g. "test_permissions".
    Passed as -k to pytest.
.PARAMETER SkipInstall
    Skip pip install step (use when deps are already up to date).
.PARAMETER PassThru
    Any additional arguments are forwarded to pytest as-is.
    Example: .\scripts\run_tests.ps1 tests/test_permissions.py -v
#>

param(
    [string]$Filter,
    [switch]$SkipInstall,
    [Parameter(ValueFromRemainingArguments)][string[]]$PassThru
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path "$PSScriptRoot/.."
Push-Location $RepoRoot
try {
    $venv   = Join-Path $RepoRoot ".venv"
    $pip    = Join-Path $venv "Scripts/pip.exe"
    $python = Join-Path $venv "Scripts/python.exe"
    $pytest = Join-Path $venv "Scripts/pytest.exe"

    # ── ensure .venv exists ──────────────────────────────────
    if (-not (Test-Path $venv)) {
        Write-Host "» Creating .venv ..." -ForegroundColor Cyan
        python -m venv $venv
    }

    # ── install deps (unless skipped) ────────────────────────
    if (-not $SkipInstall) {
        if (-not (Test-Path $pip)) {
            Write-Host "» pip not found, running ensurepip ..." -ForegroundColor Yellow
            & $python -m ensurepip --upgrade
        }
        Write-Host "» Installing/updating dependencies ..." -ForegroundColor Cyan
        & $pip install -q -r (Join-Path $RepoRoot "requirements-dev.txt")
        if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
    } else {
        Write-Host "» Skipping install (-SkipInstall)" -ForegroundColor DarkGray
    }

    # ── verify pytest is available ──────────────────────────
    if (-not (Test-Path $pytest)) {
        throw "pytest not found in .venv. Run without -SkipInstall first."
    }

    # ── build pytest args ────────────────────────────────────
    $args = @()
    if ($Filter) { $args += "-k"; $args += $Filter }
    if ($PassThru -and $PassThru.Count -gt 0) { $args += $PassThru }
    if ($args.Count -eq 0) { $args += "-q", "--tb=short" }

    # ── run tests ──────────────────────────────────────────
    $msg = if ($Filter) { "» Running tests (filter: $Filter) ..." } else { "» Running all tests ..." }
    Write-Host $msg -ForegroundColor Cyan
    & $pytest @args

    $exitCode = $LASTEXITCODE
    if ($exitCode -eq 0) {
        Write-Host "✔ All tests passed." -ForegroundColor Green
    } else {
        Write-Host "✖ Tests failed (exit code: $exitCode)." -ForegroundColor Red
    }
    exit $exitCode
}
finally {
    Pop-Location
}
