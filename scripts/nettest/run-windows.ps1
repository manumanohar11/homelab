# Network Testing Tool - Windows PowerShell Script
# Requires: Docker Desktop for Windows
#
# Usage: .\run-windows.ps1 [options]
#   Options:
#     quick   - Fast ping-only test
#     full    - Complete test (default)
#     compare - Save results for ISP comparison
#
# Example: .\run-windows.ps1 full

param(
    [ValidateSet("quick", "full", "compare")]
    [string]$Mode = "full"
)

$ErrorActionPreference = "Stop"

# Configuration
$ImageName = "nettest"
$OutputDir = "$PSScriptRoot\output"

Write-Host "Network Testing Tool - Windows" -ForegroundColor Cyan
Write-Host "===============================" -ForegroundColor Cyan
Write-Host ""

# Check Docker
Write-Host "Checking Docker..." -ForegroundColor Yellow
try {
    docker version | Out-Null
} catch {
    Write-Host "ERROR: Docker is not running!" -ForegroundColor Red
    Write-Host "Please install Docker Desktop from: https://www.docker.com/products/docker-desktop" -ForegroundColor Yellow
    exit 1
}

# Create output directory
if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir | Out-Null
}

# Build image if not exists
$ImageExists = docker images -q $ImageName 2>$null
if (-not $ImageExists) {
    Write-Host "Building Docker image (first run only)..." -ForegroundColor Yellow
    docker build -t $ImageName $PSScriptRoot
}

# Run test based on mode
Write-Host ""
Write-Host "Running $Mode test..." -ForegroundColor Green
Write-Host ""

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$HistoryFile = "$OutputDir\history_$($env:COMPUTERNAME).json"

switch ($Mode) {
    "quick" {
        docker run --rm `
            --cap-add NET_RAW `
            -v "${OutputDir}:/output" `
            $ImageName `
            --profile quick `
            --output /output
    }
    "full" {
        docker run --rm `
            --cap-add NET_RAW `
            -v "${OutputDir}:/output" `
            $ImageName `
            --profile full `
            --bufferbloat `
            --output /output
    }
    "compare" {
        docker run --rm `
            --cap-add NET_RAW `
            -v "${OutputDir}:/output" `
            $ImageName `
            --profile full `
            --bufferbloat `
            --export-csv `
            --history /output/history.json `
            --output /output
    }
}

# Find latest report
$Reports = Get-ChildItem "$OutputDir\nettest_report_*.html" | Sort-Object LastWriteTime -Descending
if ($Reports.Count -gt 0) {
    $LatestReport = $Reports[0].FullName
    Write-Host ""
    Write-Host "Report saved: $LatestReport" -ForegroundColor Green
    Write-Host ""

    $Open = Read-Host "Open report in browser? (Y/n)"
    if ($Open -ne "n" -and $Open -ne "N") {
        Start-Process $LatestReport
    }
} else {
    Write-Host "No report generated." -ForegroundColor Yellow
}
