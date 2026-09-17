@echo off
setlocal
cd /d "%~dp0"
title The iPhone Guy - Android Cleaner v0.17.1 Setup

echo ============================================================
echo   The iPhone Guy - Android Cleaner v0.17.1 Setup
echo ============================================================
echo.
echo This setup installs:
echo   - Google's Android Platform Tools (ADB)
echo   - Google's Android Build Tools used to read genuine app names
echo.
echo No Python packages or Androguard are installed.
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python was not found.
    echo Install Python 3.11 or newer and tick "Add python.exe to PATH".
    pause
    exit /b 1
)

echo Python found:
python --version
echo.

if exist "platform-tools\adb.exe" (
    echo [OK] ADB already installed.
) else (
    echo Downloading Android Platform Tools...
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://dl.google.com/android/repository/platform-tools-latest-windows.zip' -OutFile 'platform-tools.zip'"
    if errorlevel 1 (
        echo [ERROR] ADB download failed.
        pause
        exit /b 1
    )

    echo Extracting Platform Tools...
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "Expand-Archive -Path 'platform-tools.zip' -DestinationPath '.' -Force"
    if errorlevel 1 (
        echo [ERROR] ADB extraction failed.
        pause
        exit /b 1
    )
    del "platform-tools.zip" >nul 2>&1
)

echo.

if exist "build-tools\aapt2.exe" (
    echo [OK] Android Build Tools already installed.
) else if exist "build-tools\aapt.exe" (
    echo [OK] Android Build Tools already installed.
) else (
    echo Downloading Android Build Tools for genuine app-name detection...
    echo This is a one-time download and is larger than ADB.
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://dl.google.com/android/repository/build-tools_r36_windows.zip' -OutFile 'build-tools.zip'"
    if errorlevel 1 (
        echo [ERROR] Android Build Tools download failed.
        pause
        exit /b 1
    )

    echo Extracting Android Build Tools...
    if exist "_buildtools_temp" rmdir /s /q "_buildtools_temp"
    mkdir "_buildtools_temp"
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "Expand-Archive -Path 'build-tools.zip' -DestinationPath '_buildtools_temp' -Force"
    if errorlevel 1 (
        echo [ERROR] Android Build Tools extraction failed.
        pause
        exit /b 1
    )

    if exist "build-tools" rmdir /s /q "build-tools"
    mkdir "build-tools"

    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "$src = Get-ChildItem '_buildtools_temp' -Recurse -Filter 'aapt2.exe' | Select-Object -First 1; if (-not $src) { $src = Get-ChildItem '_buildtools_temp' -Recurse -Filter 'aapt.exe' | Select-Object -First 1 }; if (-not $src) { exit 2 }; Copy-Item -Path ($src.Directory.FullName + '\*') -Destination 'build-tools' -Recurse -Force"
    if errorlevel 1 (
        echo [ERROR] Could not locate Android Build Tools after extraction.
        pause
        exit /b 1
    )

    rmdir /s /q "_buildtools_temp"
    del "build-tools.zip" >nul 2>&1
)

echo.
echo ============================================================
echo Setup complete.
echo ============================================================
echo.
echo v0.17.1 includes the workshop UI and genuine Android app labels rather than
echo guessing names from package IDs.
echo.
echo Run run_cleaner.bat to start Android Cleaner.
echo.
pause
