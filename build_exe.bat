@echo off
REM ============================================================
REM  打包为单个 exe（Windows）
REM  产物：dist\案件归档.exe
REM  注意：categories.yaml 需与 exe 放在同一目录使用
REM ============================================================
setlocal

where pyinstaller >nul 2>&1
if errorlevel 1 (
    echo 未检测到 pyinstaller，正在安装依赖 ...
    pip install -r requirements.txt || goto :err
)

echo 清理旧产物 ...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
del /q 案件归档.spec 2>nul

echo 开始打包 ...
pyinstaller ^
    --onefile ^
    --windowed ^
    --name 案件归档 ^
    --icon icon.ico ^
    --collect-submodules openai ^
    --collect-submodules pdfplumber ^
    --collect-submodules docx ^
    --add-data "categories.yaml;." ^
    --add-data "style.qss;." ^
    --add-data "icon.ico;." ^
    --add-data "icon.png;." ^
    gui.py || goto :err

echo.
echo ====== 打包完成 ======
echo 可执行文件：dist\案件归档.exe
echo 请将 categories.yaml 与 style.qss 复制到 dist\ 目录一起分发
copy /y categories.yaml dist\categories.yaml >nul
copy /y style.qss dist\style.qss >nul
copy /y icon.ico dist\icon.ico >nul
echo ======================
exit /b 0

:err
echo.
echo [ERROR] 打包失败，请查看上方错误信息
exit /b 1
