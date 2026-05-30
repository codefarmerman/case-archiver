Option Explicit

Dim shell, fso, scriptDir, pythonExe, guiScript, logFile, cmd, rc

Set shell = CreateObject("WScript.Shell")
Set fso   = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
pythonExe = scriptDir & "\venv\Scripts\python.exe"
guiScript = scriptDir & "\gui.py"
logFile   = scriptDir & "\logs\launcher_output.log"

If Not fso.FileExists(pythonExe) Then
    MsgBox "python.exe NOT FOUND at:" & vbCrLf & pythonExe, 16, "Launcher"
    WScript.Quit 1
End If
If Not fso.FileExists(guiScript) Then
    MsgBox "gui.py NOT FOUND at:" & vbCrLf & guiScript, 16, "Launcher"
    WScript.Quit 1
End If

' Wrap in cmd /c so we can redirect stdout + stderr to a log file.
' Wait = True so VBS blocks until python exits, returning real exit code.
cmd = "cmd /c """"" & pythonExe & """ """ & guiScript & """ > """ & logFile & """ 2>&1"""
shell.CurrentDirectory = scriptDir
rc = shell.Run(cmd, 0, True)

If rc <> 0 Then
    Dim logText, ts
    logText = ""
    If fso.FileExists(logFile) Then
        Set ts = fso.OpenTextFile(logFile, 1)
        logText = ts.ReadAll()
        ts.Close
    End If
    MsgBox "Python exited with code " & rc & vbCrLf & vbCrLf & _
           "Output:" & vbCrLf & logText, 16, "Launcher"
End If
