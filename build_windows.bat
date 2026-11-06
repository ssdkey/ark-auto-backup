@echo off
chcp 65001 >nul
REM ============================================
REM  方舟自动备份工具 - Windows 打包脚本
REM  生成体积最小化的独立 exe
REM ============================================
echo 正在检查依赖...

python -m pip install -r requirements.txt 2>nul

echo 正在打包 exe（体积优化模式）...
python -m PyInstaller ^
  --noconfirm ^
  --onefile ^
  --windowed ^
  --name "方舟自动备份工具" ^
  --exclude-module numpy ^
  --exclude-module pandas ^
  --exclude-module matplotlib ^
  --exclude-module scipy ^
  --exclude-module PIL ^
  --clean ^
  app.py

echo.
if exist dist\"方舟自动备份工具.exe" (
    echo ✅ 打包成功：dist\方舟自动备份工具.exe
    echo 体积优化：单文件，仅含所需模块
) else (
    echo ❌ 打包失败，请检查上方错误信息
)
pause
