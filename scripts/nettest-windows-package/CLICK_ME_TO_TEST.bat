@echo off
title Network Test Tool
color 0B

echo.
echo  ==============================================================
echo                    NETWORK TEST TOOL
echo  ==============================================================
echo.
echo  This will test your internet connection and create a report.
echo.
echo  First run may take 2-5 minutes to set up.
echo  After that, tests take about 1 minute.
echo.
echo  ==============================================================
echo.
pause

:: Check if Docker is installed and running
echo.
echo  [Step 1/4] Checking Docker...
echo.

docker version >nul 2>&1
if errorlevel 1 (
    color 0C
    echo.
    echo  ==============================================================
    echo                    DOCKER NOT FOUND!
    echo  ==============================================================
    echo.
    echo  You need to install Docker Desktop first.
    echo.
    echo  Opening download page in your browser...
    echo.
    echo  ==============================================================
    echo.
    echo  After installing Docker:
    echo    1. RESTART your computer
    echo    2. Wait for Docker to start (whale icon in system tray)
    echo    3. Run this script again
    echo.
    echo  ==============================================================
    echo.
    start https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)

echo  [OK] Docker is running!
echo.

:: Create output folder
if not exist "%~dp0output" mkdir "%~dp0output"

:: Check if image exists, build if not
echo  [Step 2/4] Preparing test environment...
echo.

docker images -q nettest-friend >nul 2>&1
for /f %%i in ('docker images -q nettest-friend 2^>nul') do set IMAGE_EXISTS=%%i

if "%IMAGE_EXISTS%"=="" (
    echo  Building for first time (this takes 2-3 minutes)...
    echo.
    docker build -t nettest-friend "%~dp0nettest" >nul 2>&1
    if errorlevel 1 (
        echo  Building with visible output...
        docker build -t nettest-friend "%~dp0nettest"
    )
)

echo  [OK] Environment ready!
echo.

:: Run the test
echo  [Step 3/4] Running network tests...
echo.
echo  This will take about 1 minute. Please wait...
echo.
echo  ==============================================================

docker run --rm --cap-add NET_RAW -v "%~dp0output:/output" nettest-friend --profile full --bufferbloat --output /output

echo  ==============================================================
echo.
echo  [Step 4/4] Opening your report...
echo.

:: Find and open the latest report
for /f "delims=" %%f in ('dir /b /o-d "%~dp0output\nettest_report_*.html" 2^>nul') do (
    set LATEST_REPORT=%%f
    goto :found
)

:found
if defined LATEST_REPORT (
    echo  [OK] Report saved to: output\%LATEST_REPORT%
    echo.
    start "" "%~dp0output\%LATEST_REPORT%"
    echo  ==============================================================
    echo.
    echo                         TEST COMPLETE!
    echo.
    echo    Your report is now open in your browser.
    echo.
    echo    To share: Send the HTML file from the "output" folder
    echo              to your friend via WhatsApp, email, etc.
    echo.
    echo  ==============================================================
) else (
    color 0E
    echo  [!] Could not find report. Check the output folder manually.
)

echo.
pause
