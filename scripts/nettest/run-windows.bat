@echo off
:: Network Testing Tool - Windows Batch Script
:: Requires: Docker Desktop for Windows
::
:: Usage: run-windows.bat [quick|full|compare]

setlocal EnableDelayedExpansion

set "MODE=%~1"
if "%MODE%"=="" set "MODE=full"

set "IMAGE_NAME=nettest"
set "OUTPUT_DIR=%~dp0output"
set "DOCKER_CMD="
set "IMAGE_EXISTS="

echo.
echo Network Testing Tool - Windows
echo ===============================
echo.

:: Find Docker executable
where docker >nul 2>&1
if not errorlevel 1 (
    set "DOCKER_CMD=docker"
    goto :check_docker_running
)

:: Check common Docker Desktop installation paths
if exist "%PROGRAMFILES%\Docker\Docker\resources\bin\docker.exe" (
    set "DOCKER_CMD=%PROGRAMFILES%\Docker\Docker\resources\bin\docker.exe"
    goto :check_docker_running
)

if exist "%LOCALAPPDATA%\Docker\wsl\docker.exe" (
    set "DOCKER_CMD=%LOCALAPPDATA%\Docker\wsl\docker.exe"
    goto :check_docker_running
)

:: Docker not found
echo ERROR: Docker is not installed!
echo Please install Docker Desktop from: https://www.docker.com/products/docker-desktop
echo.
echo After installing, RESTART your computer and run this script again.
pause
exit /b 1

:check_docker_running
:: Verify Docker daemon is running
"!DOCKER_CMD!" version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is installed but not running!
    echo.
    echo Please start Docker Desktop:
    echo   1. Look for the whale icon in your system tray
    echo   2. Or search "Docker Desktop" in Start menu and open it
    echo   3. Wait 1-2 minutes for it to start
    echo   4. Run this script again
    pause
    exit /b 1
)

:: Create output directory
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

:: Build image if not exists (IMAGE_EXISTS already initialized above)
for /f %%i in ('"!DOCKER_CMD!" images -q %IMAGE_NAME% 2^>nul') do set "IMAGE_EXISTS=%%i"
if "!IMAGE_EXISTS!"=="" (
    echo Building Docker image ^(first run only^)...
    "!DOCKER_CMD!" build -t %IMAGE_NAME% "%~dp0"
    if errorlevel 1 (
        echo ERROR: Failed to build Docker image!
        pause
        exit /b 1
    )
)

echo.
echo Running %MODE% test...
echo.

:: Run test based on mode
if "%MODE%"=="quick" (
    "!DOCKER_CMD!" run --rm --cap-add NET_RAW -v "%OUTPUT_DIR%:/output" %IMAGE_NAME% --profile quick --output /output
) else if "%MODE%"=="compare" (
    "!DOCKER_CMD!" run --rm --cap-add NET_RAW -v "%OUTPUT_DIR%:/output" %IMAGE_NAME% --profile full --bufferbloat --export-csv --history /output/history.json --output /output
) else (
    "!DOCKER_CMD!" run --rm --cap-add NET_RAW -v "%OUTPUT_DIR%:/output" %IMAGE_NAME% --profile full --bufferbloat --output /output
)

echo.
echo Test complete! Check the output folder for reports.
echo.

:: List reports
dir /b "%OUTPUT_DIR%\nettest_report_*.html" 2>nul
if not errorlevel 1 (
    echo.
    set /p OPEN_REPORT="Open latest report in browser? (Y/n): "
    if /i not "!OPEN_REPORT!"=="n" (
        for /f "delims=" %%f in ('dir /b /o-d "%OUTPUT_DIR%\nettest_report_*.html"') do (
            start "" "%OUTPUT_DIR%\%%f"
            goto :done
        )
    )
)

:done
pause
