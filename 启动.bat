@echo off
chcp 65001 >nul
rem 一键启动（源码运行，用于测试，未打包）
cd /d "%~dp0"
where python >nul 2>nul && (set PY=python) || (set PY=py)
%PY% -c "import customtkinter" >nul 2>nul || (
  echo [提示] 正在安装依赖 customtkinter, requests ...
  %PY% -m pip install -r requirements.txt
)
echo 正在启动 方舟自动备份工具 ...
%PY% app.py
