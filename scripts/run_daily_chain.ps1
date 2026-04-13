# Daily pipeline: ingest -> (if new items) summarize + digest, or "no updates" email.
# Run from Task Scheduler (see docs/WINDOWS_SCHEDULER.md).
#
# Turn off without deleting the task:
#   1) Task Scheduler -> disable the task, OR
#   2) Create an empty file named "schedule_disabled" in the repo root (this script exits immediately).

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$DisableFlag = Join-Path $Root "schedule_disabled"

if (Test-Path -LiteralPath $DisableFlag) {
    Write-Host "[ai-news-aggregator] schedule_disabled present — skipping (remove file to resume)."
    exit 0
}

$DataDir = Join-Path $Root "data"
if (-not (Test-Path -LiteralPath $DataDir)) {
    New-Item -ItemType Directory -Path $DataDir | Out-Null
}
$LogFile = Join-Path $DataDir "scheduler_last_run.log"

function Write-Log([string]$Message) {
    $line = "{0} {1}" -f (Get-Date -Format "o"), $Message
    Add-Content -LiteralPath $LogFile -Value $line -Encoding utf8
    Write-Host $line
}

Set-Location -LiteralPath $Root
Write-Log "=== chain start ==="

function Invoke-Step([string]$Label, [string[]]$Args) {
    Write-Log "$Label : starting"
    & uv @Args
    if ($LASTEXITCODE -ne 0) {
        Write-Log "$Label : FAILED (exit $LASTEXITCODE)"
        exit $LASTEXITCODE
    }
    Write-Log "$Label : ok"
}

Invoke-Step "daily" @("run", "python", "-m", "app.daily")

Write-Log "=== chain complete ==="
exit 0
