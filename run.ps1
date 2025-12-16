<#
run.ps1 - Automate venv creation, dependency install, and run the pipeline.

Usage: from project root run: .\run.ps1
#>

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host "Working directory: $root"

$venvPath = Join-Path $root 'venv'

if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = 'python'
    $pyArgs = @()
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCmd = 'py'
    $pyArgs = @('-3')
} else {
    Write-Error "Python not found. Install Python 3.9+ and ensure 'python' or 'py' is on PATH."
    exit 1
}

if (-not (Test-Path $venvPath)) {
    Write-Host "Creating virtual environment at: $venvPath"
    $args = @()
    if ($pyArgs) { $args += $pyArgs }
    $args += '-m'; $args += 'venv'; $args += $venvPath
    & $pythonCmd @args
} else {
    Write-Host "Virtual environment already exists at: $venvPath"
}

Write-Host "Activating virtual environment..."
. "$venvPath\Scripts\Activate.ps1"

Write-Host "Upgrading pip and installing dependencies..."
pip install --upgrade pip
pip install -r agentic_audit/requirements.txt

Write-Host "Running pipeline..."
python -m agentic_audit.runner

Write-Host "Done. See agentic_audit/last_report.json"
