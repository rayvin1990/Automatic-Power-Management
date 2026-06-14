' Mi Smart Plug Auto Charger - Silent Startup Script
' Place this file in the Windows Startup folder for auto-start on boot
' Modify the paths below to match your actual installation

Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

userProfile = WshShell.ExpandEnvironmentStrings("%USERPROFILE%")

' Path to pythonw.exe (modify if using a different Python installation)
pythonwPath = userProfile & "\.workbuddy\binaries\python\versions\3.13.12\pythonw.exe"

' If the above path does not exist, try system PATH
If Not fso.FileExists(pythonwPath) Then
    pythonwPath = "pythonw.exe"
End If

' Path to the main script (modify to match your installation directory)
scriptPath = userProfile & "\WorkBuddy\2026-06-13-15-57-05\smart_charger.py"

' Launch silently (0=hidden window, False=don't wait)
WshShell.Run """" & pythonwPath & """ """ & scriptPath & """", 0, False
