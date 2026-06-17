@echo off
chcp 936 >nul
setlocal

echo ==========================================================
echo   Register Wake-up Battery Check Task
echo ==========================================================
echo.
echo This will create a Windows scheduled task that wakes your
echo PC every 10 minutes to check battery level and control
echo the smart plug, even when the PC is sleeping.
echo.
echo Administrator rights are required.
echo.

set "SCRIPT_DIR=%~dp0"

REM Try to find pythonw.exe
set "PYTHONW="
where pythonw >nul 2>nul
if %errorlevel% equ 0 (
    for /f "tokens=*" %%i in ('where pythonw') do set "PYTHONW=%%i"
) else (
    REM Try common paths
    if exist "%USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\pythonw.exe" (
        set "PYTHONW=%USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\pythonw.exe"
    ) else if exist "%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe" (
        set "PYTHONW=%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe"
    )
)

if "%PYTHONW%"=="" (
    echo [ERROR] pythonw.exe not found. Please add Python to PATH or install it.
    pause
    exit /b 1
)

echo Using: %PYTHONW%
echo Script: %SCRIPT_DIR%quick_check.py
echo.

REM Delete old task if exists
schtasks /Delete /TN "SmartCharger_WakeCheck" /F >nul 2>nul

REM Create the wake-up check task
REM - WakeToRun: wake the PC from sleep to run this task
REM - /SC MINUTE /MO 10: every 10 minutes
REM - /RI 10: repeat interval 10 minutes
REM - /DU 9999: repeat for essentially forever
REM - /ET: no end time
REM Using pythonw.exe to avoid console window flash

schtasks /Create /TN "SmartCharger_WakeCheck" /TR "\"%PYTHONW%\" \"%SCRIPT_DIR%quick_check.py\"" /SC MINUTE /MO 10 /RI 10 /DU 9999:59:59 /F /RL HIGHEST /ENABLE

if %errorlevel% equ 0 (
    echo.
    echo [OK] Wake-up check task created successfully.
    echo.
    echo Now enabling WakeToRun flag...
    
    REM Enable WakeToRun via registry (schtasks doesn't support this flag directly)
    REM The task XML needs <WakeToRun>true</WakeToRun>
    
    REM Export, modify, and re-import the task
    set "TMPXML=%TEMP%\SmartCharger_WakeCheck.xml"
    schtasks /Query /TN "SmartCharger_WakeCheck" /XML > "%TMPXML%" 2>nul
    
    if exist "%TMPXML%" (
        REM Add WakeToRun=true to the XML
        powershell -Command "(Get-Content '%TMPXML%') -replace '<WakeToRun>false</WakeToRun>', '<WakeToRun>true</WakeToRun>' -replace '</Settings>', '<WakeToRun>true</WakeToRun></Settings>' | Set-Content '%TMPXML%'"
        
        REM Re-import the modified task
        schtasks /Create /TN "SmartCharger_WakeCheck" /XML "%TMPXML%" /F >nul 2>nul
        
        if %errorlevel% equ 0 (
            echo [OK] WakeToRun enabled. PC will wake from sleep for battery checks.
        ) else (
            echo [WARN] Could not enable WakeToRun. Task is registered but won't wake PC from sleep.
            echo        You can manually enable "Wake the computer to run this task" in Task Scheduler.
        )
        
        del "%TMPXML%" >nul 2>nul
    ) else (
        echo [WARN] Could not modify task XML. WakeToRun may not be enabled.
    )
) else (
    echo.
    echo [ERROR] Failed to create scheduled task.
    echo Make sure you run this script as Administrator.
)

echo.
echo ==========================================================
echo   Verifying task registration...
echo ==========================================================
echo.
schtasks /Query /TN "SmartCharger_WakeCheck" /FO LIST 2>nul

echo.
echo Done. Press any key to exit...
pause >nul
