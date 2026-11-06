@echo off
chcp 65001 >nul
REM ============================================
REM  方舟自动备份工具 - 一键生成安装向导
REM  前置：Windows + Inno Setup 6
REM         https://jrsoftware.org/isdl.php
REM ============================================
echo [1/2] 生成单文件 exe（体积优化）...
call build_windows.bat
if not exist "dist\方舟自动备份工具.exe" (
    echo ❌ 未找到 exe，打包终止
    pause
    exit /b 1
)

echo [2/2] 调用 Inno Setup 生成安装向导...
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
    echo ❌ 未找到 Inno Setup，请先安装：https://jrsoftware.org/isdl.php
    pause
    exit /b 1
)

"%ISCC%" installer.iss
echo.
if exist "dist\方舟自动备份工具_Setup.exe" (
    echo ✅ 安装向导生成成功：dist\方舟自动备份工具_Setup.exe
) else (
    echo ❌ 安装向导生成失败，请检查上方错误
)
pause
