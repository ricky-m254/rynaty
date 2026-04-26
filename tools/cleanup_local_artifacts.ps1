param(
    [switch]$Apply
)

$repoRoot = Split-Path -Parent $PSScriptRoot
$artifactRoot = Join-Path $repoRoot "artifacts"

if (-not (Test-Path -LiteralPath $artifactRoot)) {
    Write-Host "No root artifacts directory found at $artifactRoot"
    exit 0
}

$patterns = @(
    "temp_pg_*",
    "cdp-*",
    "chrome-*",
    "*.log",
    "*.zip"
)

$targets = @()
foreach ($pattern in $patterns) {
    $targets += Get-ChildItem -Path (Join-Path $artifactRoot $pattern) -Force -ErrorAction SilentlyContinue
}

$targets = $targets | Sort-Object FullName -Unique

if (-not $targets) {
    Write-Host "No matching runtime artifacts found under $artifactRoot"
    exit 0
}

Write-Host "Artifact root: $artifactRoot"
Write-Host ("Mode: " + ($(if ($Apply) { "apply" } else { "preview" })))

foreach ($item in $targets) {
    $resolved = $item.FullName
    if (-not $resolved.StartsWith($artifactRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        Write-Warning "Skipping unexpected path outside artifact root: $resolved"
        continue
    }

    if ($Apply) {
        Remove-Item -LiteralPath $resolved -Recurse -Force
        Write-Host "Removed $resolved"
    } else {
        Write-Host "Would remove $resolved"
    }
}
