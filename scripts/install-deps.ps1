# 安装 mind-sync Python 依赖（Windows PowerShell）
# 用法: .\scripts\install-deps.ps1 [-Tools] [-Dev]
param(
    [switch]$Tools,
    [switch]$Dev
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "Python:" (python --version)
Write-Host "Installing API dependencies..."
python -m pip install --upgrade pip
python -m pip install --only-binary=:all: pydantic-core 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Note: pydantic-core wheel install skipped or failed; pip may compile from source (slow on 3.14)."
}
python -m pip install -r requirements.txt

if ($Tools) {
    Write-Host "Installing CLI + MCP..."
    python -m pip install -r requirements-tools.txt
}

if ($Dev) {
    Write-Host "Installing dev (pytest, pip-audit)..."
    python -m pip install -r requirements-dev.txt
}

Write-Host "Done. Verify: python scripts/check_test_env.py"
