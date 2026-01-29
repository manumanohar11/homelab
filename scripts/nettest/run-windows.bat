@echo off
:: Network Testing Tool - Windows Batch Script
:: Requires: Docker Desktop for Windows
::
:: Usage: run-windows.bat [quick|full|compare]

setlocal EnableDelayedExpansion

set MODE=%1
if "%MODE%"=="" set MODE=full

set IMAGE_NAME=nettest
set OUTPUT_DIR=%~dp0output

echo.
echo Network Testing Tool - Windows
echo ===============================
echo.

:: Check Docker
docker version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not running!
    echo Please install Docker Desktop from: https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)

:: Create output directory
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

:: Build image if not exists
for /f %%i in ('docker images -q %IMAGE_NAME% 2^>nul') do set IMAGE_EXISTS=%%i
if "%IMAGE_EXISTS%"=="" (
    echo Building Docker image ^(first run only^)...
    docker build -t %IMAGE_NAME% %~dp0
)

echo.
echo Running %MODE% test...
echo.

:: Run test based on mode
if "%MODE%"=="quick" (
    docker run --rm --cap-add NET_RAW -v "%OUTPUT_DIR%:/output" %IMAGE_NAME% --profile quick --output /output
) else if "%MODE%"=="compare" (
    docker run --rm --cap-add NET_RAW -v "%OUTPUT_DIR%:/output" %IMAGE_NAME% --profile full --bufferbloat --export-csv --history /output/history.json --output /output
) else (
    docker run --rm --cap-add NET_RAW -v "%OUTPUT_DIR%:/output" %IMAGE_NAME% --profile full --bufferbloat --output /output
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
