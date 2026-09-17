@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 start.py %*
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo 请先安装 Python 3.11 或以上版本，并勾选 Add Python to PATH。
    pause
    exit /b 1
  )
  python start.py %*
)
if errorlevel 1 pause
