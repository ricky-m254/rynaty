param(
    [Parameter(Mandatory = $true)]
    [string]$AppDir,

    [Parameter(Mandatory = $true)]
    [string]$PythonExe,

    [Parameter(Mandatory = $true)]
    [string]$AdminUsername,

    [Parameter(Mandatory = $true)]
    [string]$NewPrimaryKey,

    [Parameter(Mandatory = $true)]
    [string]$OldPrimaryKey,

    [string]$KeyPrefix,
    [string]$LogDir,
    [switch]$RunLive
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Title)
    Write-Host ""
    Write-Host ("=" * 80)
    Write-Host $Title
    Write-Host ("=" * 80)
}

function Invoke-LoggedCommand {
    param(
        [string]$Label,
        [string[]]$Args
    )

    Write-Step $Label
    Write-Host ("Command: " + $PythonExe + " " + ($Args -join " "))
    & $PythonExe @Args
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $Label"
    }
}

if (-not $LogDir) {
    $repoRoot = Split-Path -Parent $PSScriptRoot
    $LogDir = Join-Path $repoRoot "artifacts\operator_runs"
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$stamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$logPath = Join-Path $LogDir ("{0}_secret_rotation_{1}.log" -f $stamp, $AdminUsername)

Start-Transcript -Path $logPath -Force | Out-Null

try {
    Set-Location $AppDir

    if (-not (Test-Path -LiteralPath $PythonExe)) {
        throw "Python executable not found: $PythonExe"
    }

    $env:DJANGO_TENANT_SECRET_KEYS = "$NewPrimaryKey,$OldPrimaryKey"

    Write-Step "Secret Key Ring Configured"
    Write-Host ("AppDir: " + $AppDir)
    Write-Host ("PythonExe: " + $PythonExe)
    Write-Host ("AdminUsername: " + $AdminUsername)
    Write-Host ("Key entries configured: 2")
    Write-Host ("Primary key length: " + $NewPrimaryKey.Length)
    Write-Host ("Secondary key length: " + $OldPrimaryKey.Length)
    if ($KeyPrefix) {
        Write-Host ("Scoped key prefix: " + $KeyPrefix)
    } else {
        Write-Host "Scoped key prefix: <all tenant secrets>"
    }

    Invoke-LoggedCommand -Label "Check tenant secret migration" -Args @(
        "manage.py",
        "showmigrations",
        "school"
    )

    Write-Step "Confirm migration output includes 0065_tenantsecret_encrypted_store"
    Write-Host "Manual check: verify the migration above is listed as applied."

    Invoke-LoggedCommand -Label "Check rotate_tenant_secrets command help" -Args @(
        "manage.py",
        "help",
        "rotate_tenant_secrets"
    )

    Invoke-LoggedCommand -Label "Run Django system check" -Args @(
        "manage.py",
        "check"
    )

    $dryRunArgs = @(
        "manage.py",
        "rotate_tenant_secrets",
        "--dry-run",
        "--actor-username",
        $AdminUsername
    )
    if ($KeyPrefix) {
        $dryRunArgs += @("--key-prefix", $KeyPrefix)
    }
    Invoke-LoggedCommand -Label "Run secret rotation dry-run" -Args $dryRunArgs

    if ($RunLive) {
        $liveArgs = @(
            "manage.py",
            "rotate_tenant_secrets",
            "--actor-username",
            $AdminUsername
        )
        if ($KeyPrefix) {
            $liveArgs += @("--key-prefix", $KeyPrefix)
        }
        Invoke-LoggedCommand -Label "Run live secret rotation" -Args $liveArgs
    } else {
        Write-Step "Live rotation skipped"
        Write-Host "Run again with -RunLive after reviewing the dry-run output."
    }

    Write-Step "Next manual checks"
    Write-Host "1. Confirm finance settings page loads."
    Write-Host "2. Confirm M-Pesa test connection succeeds."
    Write-Host "3. Confirm Stripe connection test succeeds if Stripe is enabled."
    Write-Host "4. Continue with LIVE_PAYMENT_VALIDATION_RUN_SEQUENCE.md."
}
finally {
    Stop-Transcript | Out-Null
    Write-Host ""
    Write-Host ("Transcript saved to: " + $logPath)
}
