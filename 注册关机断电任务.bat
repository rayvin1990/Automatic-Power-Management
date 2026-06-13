@echo off
chcp 65001 >nul
setlocal

echo ==========================================================
echo   Mi Smart Plug - Register Shutdown and Startup Tasks
echo ==========================================================
echo.
echo Registering Windows scheduled tasks. Administrator rights are recommended.
echo.

set "SCRIPT_DIR=%~dp0"
set "PYTHON_CMD="

where py >nul 2>nul
if %errorlevel% equ 0 (
    set "PYTHON_CMD=py"
) else (
    where python >nul 2>nul
    if %errorlevel% equ 0 (
        set "PYTHON_CMD=python"
    )
)

if "%PYTHON_CMD%"=="" (
    echo [ERROR] Python was not found in PATH.
    echo Install Python 3.8+ or add it to PATH, then run this script again.
    pause
    exit /b 1
)

echo Using Python command: %PYTHON_CMD%
echo.

schtasks /Create /TN "SmartCharger_ShutdownTurnOff" /TR "\"%PYTHON_CMD%\" \"%SCRIPT_DIR%shutdown_turn_off_plug.py\"" /SC ONEVENT /EC System /MO "*[System[Provider[@Name='User32'] and EventID=1074]]" /F

if %errorlevel% equ 0 (
    echo.
    echo [OK] Shutdown event task registered.
) else (
    echo.
    echo [WARN] Event trigger failed. Trying logoff trigger...
    schtasks /Create /TN "SmartCharger_ShutdownTurnOff" /TR "\"%PYTHON_CMD%\" \"%SCRIPT_DIR%shutdown_turn_off_plug.py\"" /SC ONLOGOFF /F
    if %errorlevel% equ 0 (
        echo.
        echo [OK] Logoff task registered.
    ) else (
        echo.
        echo [WARN] Auto-register failed.
        echo smart_charger.py still has built-in shutdown protection while it is running.
    )
)

echo.
echo ==========================================================
echo   Registering startup task...
echo ==========================================================
echo.

schtasks /Create /TN "SmartCharger_AutoStart" /TR "wscript.exe \"%SCRIPT_DIR%启动智能充电(静默).vbs\"" /SC ONLOGON /F /RL LIMITED

if %errorlevel% equ 0 (
    echo [OK] Auto-start on login registered.
) else (
    echo [WARN] Auto-start registration failed.
)

echo.
echo Done. Press any key to exit...
pause >nul
