# Create desktop shortcut for Case Archiver GUI (via VBS launcher)
$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Launcher   = Join-Path $ProjectDir "launcher.vbs"
$PythonW    = Join-Path $ProjectDir "venv\Scripts\pythonw.exe"
$GuiScript  = Join-Path $ProjectDir "gui.py"
$IconSrc    = Join-Path $ProjectDir "venv\Scripts\python.exe"

if (-not (Test-Path $Launcher))  { Write-Host "[ERROR] launcher.vbs missing" -ForegroundColor Red; Read-Host; exit 1 }
if (-not (Test-Path $GuiScript)) { Write-Host "[ERROR] gui.py missing"      -ForegroundColor Red; Read-Host; exit 1 }

$Desktop = [Environment]::GetFolderPath("Desktop")
$LnkPath = Join-Path $Desktop "AAA.lnk"

# remove stale shortcut first
$cn = Join-Path $Desktop "案件归档.lnk"
if (Test-Path $cn)      { Remove-Item $cn -Force }
if (Test-Path $LnkPath) { Remove-Item $LnkPath -Force }

$WScript = New-Object -ComObject WScript.Shell
$Shortcut = $WScript.CreateShortcut($LnkPath)
$Shortcut.TargetPath       = "wscript.exe"
$Shortcut.Arguments        = '"' + $Launcher + '"'
$Shortcut.WorkingDirectory = $ProjectDir
$Shortcut.WindowStyle      = 1
$Shortcut.Description      = "Case Archiver v2.1"
$Shortcut.IconLocation     = $IconSrc + ",0"
$Shortcut.Save()

Rename-Item -Path $LnkPath -NewName "案件归档.lnk"

Write-Host ""
Write-Host "[OK] Shortcut recreated at: $cn" -ForegroundColor Green
Write-Host ""
Read-Host "Press Enter to close"
