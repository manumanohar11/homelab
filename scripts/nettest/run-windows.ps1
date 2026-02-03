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
$DockerCmd = $null

Write-Host "Network Testing Tool - Windows" -ForegroundColor Cyan
Write-Host "===============================" -ForegroundColor Cyan
Write-Host ""

# Find Docker executable
Write-Host "Checking Docker..." -ForegroundColor Yellow

# Try docker in PATH first
$DockerInPath = Get-Command docker -ErrorAction SilentlyContinue
if ($DockerInPath) {
    $DockerCmd = "docker"
}

# Check common Docker Desktop installation paths
if (-not $DockerCmd) {
    $DockerPaths = @(
        "$env:ProgramFiles\Docker\Docker\resources\bin\docker.exe",
        "$env:LOCALAPPDATA\Docker\wsl\docker.exe"
    )
    foreach ($path in $DockerPaths) {
        if (Test-Path $path) {
            $DockerCmd = $path
            break
        }
    }
}

# Docker not found
if (-not $DockerCmd) {
    Write-Host "ERROR: Docker is not installed!" -ForegroundColor Red
    Write-Host "Please install Docker Desktop from: https://www.docker.com/products/docker-desktop" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "After installing, RESTART your computer and run this script again." -ForegroundColor Yellow
    exit 1
}

# Verify Docker is running
try {
    & $DockerCmd version 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Docker not running" }
} catch {
    Write-Host "ERROR: Docker is installed but not running!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please start Docker Desktop:" -ForegroundColor Yellow
    Write-Host "  1. Look for the whale icon in your system tray" -ForegroundColor Yellow
    Write-Host "  2. Or search 'Docker Desktop' in Start menu and open it" -ForegroundColor Yellow
    Write-Host "  3. Wait 1-2 minutes for it to start" -ForegroundColor Yellow
    Write-Host "  4. Run this script again" -ForegroundColor Yellow
    exit 1
}

# Create output directory
if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir | Out-Null
}

# Build image if not exists
$ImageExists = & $DockerCmd images -q $ImageName 2>$null
if (-not $ImageExists) {
    Write-Host "Building Docker image (first run only)..." -ForegroundColor Yellow
    & $DockerCmd build -t $ImageName $PSScriptRoot
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to build Docker image!" -ForegroundColor Red
        exit 1
    }
}

# Run test based on mode
Write-Host ""
Write-Host "Running $Mode test..." -ForegroundColor Green
Write-Host ""

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$HistoryFile = "$OutputDir\history_$($env:COMPUTERNAME).json"

switch ($Mode) {
    "quick" {
        & $DockerCmd run --rm `
            --cap-add NET_RAW `
            -v "${OutputDir}:/output" `
            $ImageName `
            --profile quick `
            --output /output
    }
    "full" {
        & $DockerCmd run --rm `
            --cap-add NET_RAW `
            -v "${OutputDir}:/output" `
            $ImageName `
            --profile full `
            --bufferbloat `
            --output /output
    }
    "compare" {
        & $DockerCmd run --rm `
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
