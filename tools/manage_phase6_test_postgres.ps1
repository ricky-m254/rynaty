param(
    [ValidateSet("start", "status", "stop", "reset")]
    [string]$Action = "status"
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

$repoRoot = Split-Path -Parent $PSScriptRoot
$artifactRoot = Join-Path $repoRoot "artifacts"
$dataDir = Join-Path $artifactRoot "temp_pg_phase6_tests"
$templateDataDir = Join-Path $artifactRoot "temp_pg_accounting_tests_clean"
$stateFile = Join-Path $artifactRoot "temp_pg_phase6_tests.runtime.json"
$serverLog = Join-Path $artifactRoot "temp_pg_phase6_tests.server.log"
$stdoutLog = Join-Path $artifactRoot "temp_pg_phase6_tests.stdout.log"
$stderrLog = Join-Path $artifactRoot "temp_pg_phase6_tests.stderr.log"

$postgresBin = "D:\postgress\bin"
$pgCtl = Join-Path $postgresBin "pg_ctl.exe"
$initdb = Join-Path $postgresBin "initdb.exe"
$postgres = Join-Path $postgresBin "postgres.exe"
$psql = Join-Path $postgresBin "psql.exe"
$createdb = Join-Path $postgresBin "createdb.exe"

$dbHost = "127.0.0.1"
$port = "55437"
$user = "postgres"
$database = "test_sms_school_db"

function Assert-ToolExists {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Required Postgres tool not found: $Path"
    }
}

function Resolve-SafePath {
    param(
        [string]$Path,
        [string]$Root
    )

    $resolvedPath = [System.IO.Path]::GetFullPath($Path)
    $resolvedRoot = [System.IO.Path]::GetFullPath($Root)

    if (-not $resolvedPath.StartsWith($resolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to operate outside artifact root: $resolvedPath"
    }

    return $resolvedPath
}

function Ensure-ArtifactRoot {
    if (-not (Test-Path -LiteralPath $artifactRoot)) {
        New-Item -ItemType Directory -Path $artifactRoot | Out-Null
    }
}

function Invoke-NativeCommand {
    param(
        [string]$FilePath,
        [string[]]$Arguments
    )

    $previousErrorAction = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        $output = & $FilePath @Arguments 2>&1
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorAction
    }

    return [pscustomobject]@{
        Code = $code
        Output = ($output | Out-String).Trim()
    }
}

function Get-PidFilePath {
    return Join-Path $dataDir "postmaster.pid"
}

function Get-PgCtlStatus {
    return Invoke-NativeCommand -FilePath $pgCtl -Arguments @("-D", $dataDir, "status")
}

function Load-State {
    if (-not (Test-Path -LiteralPath $stateFile)) {
        return $null
    }

    return (Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json)
}

function Save-State {
    param(
        [string]$LaunchMethod,
        [int]$ProcessId = 0
    )

    $payload = [ordered]@{
        launchMethod = $LaunchMethod
        pid = $ProcessId
        dataDir = $dataDir
        port = $port
        updatedAt = (Get-Date).ToString("o")
    }
    $payload | ConvertTo-Json | Set-Content -LiteralPath $stateFile -Encoding UTF8
}

function Clear-State {
    if (Test-Path -LiteralPath $stateFile) {
        Remove-Item -LiteralPath $stateFile -Force
    }
}

function Remove-StalePidFile {
    $pidFile = Get-PidFilePath
    if (Test-Path -LiteralPath $pidFile) {
        $pidText = (Get-Content -LiteralPath $pidFile -TotalCount 1 -ErrorAction SilentlyContinue | Out-String).Trim()
        if ($pidText -match '^\d+$') {
            Stop-Process -Id ([int]$pidText) -Force -ErrorAction SilentlyContinue
        }
        $resolvedPidFile = Resolve-SafePath -Path $pidFile -Root $artifactRoot
        Remove-Item -LiteralPath $resolvedPidFile -Force
    }
}

function Test-ClusterReady {
    $result = Invoke-NativeCommand -FilePath $psql -Arguments @("-h", $dbHost, "-p", $port, "-U", $user, "-d", "postgres", "-tAc", "SELECT 1")
    return ($result.Code -eq 0 -and $result.Output -eq "1")
}

function Wait-ClusterReady {
    param([int]$TimeoutSeconds = 120)

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-ClusterReady) {
            return $true
        }
        Start-Sleep -Seconds 2
    }

    return $false
}

function Ensure-DatabaseExists {
    $exists = Invoke-NativeCommand -FilePath $psql -Arguments @("-h", $dbHost, "-p", $port, "-U", $user, "-d", "postgres", "-tAc", "SELECT 1 FROM pg_database WHERE datname = '$database'")
    if ($exists.Code -ne 0) {
        throw "Unable to query cluster readiness for database existence."
    }

    if ($exists.Output -eq "1") {
        return
    }

    $create = Invoke-NativeCommand -FilePath $createdb -Arguments @("-h", $dbHost, "-p", $port, "-U", $user, $database)
    if ($create.Code -ne 0) {
        throw "Failed to create database $database on temp cluster."
    }
}

function Ensure-ClusterInitialized {
    Ensure-ArtifactRoot
    Assert-ToolExists -Path $initdb

    if (Test-Path -LiteralPath (Join-Path $dataDir "PG_VERSION")) {
        return
    }

    $resolvedDataDir = Resolve-SafePath -Path $dataDir -Root $artifactRoot
    if (Test-Path -LiteralPath $resolvedDataDir) {
        Remove-Item -LiteralPath $resolvedDataDir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $resolvedDataDir | Out-Null

    $initdbResult = Invoke-NativeCommand -FilePath $initdb -Arguments @("-D", $resolvedDataDir, "-A", "trust", "-U", $user, "-E", "UTF8")
    if ($initdbResult.Code -eq 0) {
        return
    }

    Write-Warning "initdb failed for $resolvedDataDir; attempting clean template fallback."

    if (-not (Test-Path -LiteralPath (Join-Path $templateDataDir "PG_VERSION"))) {
        throw "initdb failed and no clean template cluster is available. Output: $($initdbResult.Output)"
    }

    $resolvedTemplateDir = Resolve-SafePath -Path $templateDataDir -Root $artifactRoot
    Remove-Item -LiteralPath $resolvedDataDir -Recurse -Force
    Copy-Item -LiteralPath $resolvedTemplateDir -Destination $resolvedDataDir -Recurse

    Get-ChildItem -Path $resolvedDataDir -Filter "postmaster.pid*" -Force -ErrorAction SilentlyContinue | ForEach-Object {
        Remove-Item -LiteralPath $_.FullName -Force
    }
}

function Start-WithPgCtl {
    return Invoke-NativeCommand -FilePath $pgCtl -Arguments @("-D", $dataDir, "-l", $serverLog, "-o", """-p $port""", "-w", "start")
}

function Start-WithDirectPostgres {
    if (Test-Path -LiteralPath $stdoutLog) {
        Remove-Item -LiteralPath $stdoutLog -Force
    }
    if (Test-Path -LiteralPath $stderrLog) {
        Remove-Item -LiteralPath $stderrLog -Force
    }

    $process = Start-Process `
        -FilePath $postgres `
        -ArgumentList @("-D", $dataDir, "-p", $port, "-h", $dbHost) `
        -RedirectStandardOutput $stdoutLog `
        -RedirectStandardError $stderrLog `
        -WindowStyle Hidden `
        -PassThru

    if (-not (Wait-ClusterReady -TimeoutSeconds 600)) {
        if (-not $process.HasExited) {
            Stop-Process -Id $process.Id -Force
        }
        throw "postgres.exe fallback start did not become ready on ${dbHost}:${port}"
    }

    Save-State -LaunchMethod "direct" -ProcessId $process.Id
}

function Start-Cluster {
    Assert-ToolExists -Path $pgCtl
    Assert-ToolExists -Path $psql
    Assert-ToolExists -Path $postgres
    Assert-ToolExists -Path $createdb

    Ensure-ClusterInitialized

    $status = Get-PgCtlStatus
    if ($status.Code -eq 0 -and (Test-ClusterReady)) {
        Ensure-DatabaseExists
        if (-not (Load-State)) {
            Save-State -LaunchMethod "pg_ctl"
        }
        Write-Host "Cluster already running on ${dbHost}:${port}"
        return
    }

    if ($status.Code -ne 0) {
        Remove-StalePidFile
    }

    $pgCtlStart = Start-WithPgCtl
    if ($pgCtlStart.Code -eq 0 -and (Wait-ClusterReady -TimeoutSeconds 180)) {
        Save-State -LaunchMethod "pg_ctl"
        Ensure-DatabaseExists
        Write-Host "Cluster started with pg_ctl on ${dbHost}:${port}"
        return
    }

    Write-Warning "pg_ctl start failed or did not become ready; falling back to direct postgres.exe startup."
    Start-WithDirectPostgres
    Ensure-DatabaseExists
    Write-Host "Cluster started with direct postgres.exe on ${dbHost}:${port}"
}

function Stop-Cluster {
    Assert-ToolExists -Path $pgCtl

    $status = Get-PgCtlStatus
    if ($status.Code -eq 0) {
        $stopResult = Invoke-NativeCommand -FilePath $pgCtl -Arguments @("-D", $dataDir, "-m", "fast", "stop")
        if ($stopResult.Code -eq 0) {
            Clear-State
            Write-Host "Cluster stopped with pg_ctl."
            return
        }
    }

    $state = Load-State
    if ($null -ne $state -and $state.launchMethod -eq "direct" -and [int]$state.pid -gt 0) {
        $processId = [int]$state.pid
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction SilentlyContinue
        if ($null -ne $proc) {
            $commandLine = $proc.CommandLine
            if ($commandLine -and $commandLine.IndexOf($dataDir, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
                Stop-Process -Id $processId -Force
                Clear-State
                Write-Host "Cluster stopped via recorded direct postgres.exe PID."
                return
            }
            throw "Refusing to stop PID $processId because it is not bound to $dataDir"
        }
    }

    Remove-StalePidFile
    Clear-State
    Write-Host "No running cluster found."
}

function Show-Status {
    $status = Get-PgCtlStatus
    $state = Load-State
    $launchMethod = if ($null -ne $state) { $state.launchMethod } else { "unknown" }
    $isReady = Test-ClusterReady

    Write-Host "Data dir: $dataDir"
    Write-Host "Host: $dbHost"
    Write-Host "Port: $port"
    Write-Host "Launch method: $launchMethod"
    Write-Host ("Running: " + ($(if ($status.Code -eq 0) { "yes" } else { "no" })))
    Write-Host ("Ready: " + ($(if ($isReady) { "yes" } else { "no" })))

    if ($status.Output) {
        Write-Host "pg_ctl: $($status.Output)"
    }
}

function Reset-Cluster {
    Stop-Cluster

    if (Test-Path -LiteralPath $dataDir) {
        $resolvedDataDir = Resolve-SafePath -Path $dataDir -Root $artifactRoot
        Remove-Item -LiteralPath $resolvedDataDir -Recurse -Force
    }

    Clear-State
    Write-Host "Removed temp cluster at $dataDir"
}

switch ($Action) {
    "start" { Start-Cluster }
    "status" { Show-Status }
    "stop" { Stop-Cluster }
    "reset" { Reset-Cluster }
}
