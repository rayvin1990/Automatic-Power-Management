@echo off
chcp 936 >nul
echo ==========================================================
echo   Mi Smart Plug - Register Shutdown and Startup Tasks
echo ==========================================================
echo.
echo Registering Windows scheduled task (admin required)...
echo.
echo NOTE: Please edit the Python path below to match your system!
echo.

REM === Edit these paths to match your Python installation ===
set PYTHONW=C:\Python313\pythonw.exe
set PYTHON=C:\Python313\python.exe
set SCRIPT_DIR=%~dp0
REM ==========================================================

schtasks /Create /TN "SmartCharger_ShutdownTurnOff" /TR "\"%PYTHON%\" \"%SCRIPT_DIR%shutdown_turn_off_plug.py\"" /SC ONEVENT /EC System /MO "*[System[Provider[@Name='User32'] and EventID=1074]]" /F

if %errorlevel% equ 0 (
    echo.
    echo [OK] Shutdown task registered!
) else (
    echo.
    echo [!] Event trigger failed, trying OnLogoff...
    schtasks /Create /TN "SmartCharger_ShutdownTurnOff" /TR "\"%PYTHON%\" \"%SCRIPT_DIR%shutdown_turn_off_plug.py\"" /SC ONLOGOFF /F
    if %errorlevel% equ 0 (
        echo.
        echo [OK] Logoff task registered!
    ) else (
        echo.
        echo [!] Auto-register failed.
        echo     smart_charger.py has built-in shutdown protection.
        echo     It will auto power-off the plug if it is running.
    )
)

echo.
echo ==========================================================
echo   Registering startup task...
echo ==========================================================
echo.

schtasks /Create /TN "SmartCharger_AutoStart" /TR "wscript.exe \"%SCRIPT_DIR%启动智能充电(静默).vbs\"" /SC ONLOGON /F /RL LIMITED

if %errorlevel% equ 0 (
    echo [OK] Auto-start on login registered!
) else (
    echo [!] Auto-start registration failed.
)

echo.
echo ==========================================================
echo Done. Press any key to exit...
pause >nul
