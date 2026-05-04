param(
    [switch]$StopAfter
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $repoRoot "sms-backend"
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$clusterHelper = Join-Path $repoRoot "tools\manage_phase6_test_postgres.ps1"
$stdoutLog = Join-Path $repoRoot "artifacts\finance_phase6_tests.stdout.log"
$stderrLog = Join-Path $repoRoot "artifacts\finance_phase6_tests.stderr.log"

$testLabels = @(
    "school.test_phase6_architecture_guardrails",
    "school.test_phase6_finance_reference_activation_prep",
    "school.test_phase6_finance_report_activation_prep",
    "school.test_phase6_finance_billing_activation_prep",
    "school.test_phase6_finance_receivables_activation_prep",
    "school.test_phase6_finance_governance_activation_prep",
    "school.test_phase6_finance_collection_ops_activation_prep",
    "school.test_phase6_finance_accounting_activation_prep",
    "school.test_phase6_finance_write_activation_prep"
)

if (-not (Test-Path -LiteralPath $python)) {
    throw "Repo venv Python not found at $python"
}

if (-not (Test-Path -LiteralPath $clusterHelper)) {
    throw "Cluster helper not found at $clusterHelper"
}

function Invoke-ClusterHelper {
    param(
        [ValidateSet("start", "status", "stop", "reset")]
        [string]$Action
    )

    & powershell -ExecutionPolicy Bypass -File $clusterHelper -Action $Action
    if ($LASTEXITCODE -ne 0) {
        throw "Cluster helper action '$Action' failed."
    }
}

try {
    Invoke-ClusterHelper -Action start
} catch {
    Write-Warning "Finance phase-6 temp cluster start failed; resetting disposable cluster and retrying once."
    Invoke-ClusterHelper -Action reset
    Invoke-ClusterHelper -Action start
}

Set-Location $backend

$env:DATABASE_URL = "postgresql://postgres@127.0.0.1:55437/test_sms_school_db"
$env:DJANGO_DEBUG = "true"
$env:DJANGO_ALLOW_INSECURE_DEFAULTS = "true"
$env:PYTHONUNBUFFERED = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

if (Test-Path -LiteralPath $stdoutLog) {
    Remove-Item -LiteralPath $stdoutLog -Force
}
if (Test-Path -LiteralPath $stderrLog) {
    Remove-Item -LiteralPath $stderrLog -Force
}

$arguments = @(
    "manage.py",
    "test"
) + $testLabels + @(
    "--keepdb",
    "--noinput",
    "--verbosity",
    "1"
)

$process = Start-Process `
    -FilePath $python `
    -ArgumentList $arguments `
    -RedirectStandardOutput $stdoutLog `
    -RedirectStandardError $stderrLog `
    -NoNewWindow `
    -PassThru `
    -Wait
$exitCode = $process.ExitCode

Write-Host "stdout log: $stdoutLog"
Write-Host "stderr log: $stderrLog"

if ($StopAfter) {
    Invoke-ClusterHelper -Action stop
}

if ($exitCode -ne 0) {
    if (Test-Path -LiteralPath $stderrLog) {
        Write-Host "--- stderr tail ---"
        Get-Content -LiteralPath $stderrLog -Tail 80
    }
    if (Test-Path -LiteralPath $stdoutLog) {
        Write-Host "--- stdout tail ---"
        Get-Content -LiteralPath $stdoutLog -Tail 80
    }
    exit $exitCode
}

if (Test-Path -LiteralPath $stdoutLog) {
    Get-Content -LiteralPath $stdoutLog -Tail 40
}
