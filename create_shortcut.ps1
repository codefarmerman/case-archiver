# Create desktop shortcut for Case Archiver GUI (via VBS launcher)
$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Launcher   = Join-Path $ProjectDir "launcher.vbs"
$PythonW    = Join-Path $ProjectDir "venv\Scripts\pythonw.exe"
$GuiScript  = Join-Path $ProjectDir "gui.py"
# 优先用项目自带图标，缺失时回退到 python 解释器图标
$IconIco    = Join-Path $ProjectDir "icon.ico"
if (Test-Path $IconIco) { $IconSrc = $IconIco } else { $IconSrc = Join-Path $ProjectDir "venv\Scripts\python.exe" }

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
$Shortcut.Description      = "律师案件归档 Case Archiver"
$Shortcut.IconLocation     = $IconSrc + ",0"
$Shortcut.Save()

Rename-Item -Path $LnkPath -NewName "案件归档.lnk"

Write-Host ""
Write-Host "[OK] Shortcut recreated at: $cn" -ForegroundColor Green
Write-Host ""
Read-Host "Press Enter to close"
