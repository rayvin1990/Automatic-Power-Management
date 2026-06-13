' Mi Smart Plug Auto Charger - Silent Launcher
' Uses pythonw.exe for no-console background execution
' Edit the path below to match your Python installation

Dim fso, scriptDir
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

Dim WshShell
Set WshShell = CreateObject("WScript.Shell")

' Try pythonw.exe first (no console window), fall back to python.exe
WshShell.Run "pythonw.exe """ & scriptDir & "\smart_charger.py""", 0, False
