@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
rem 用法：把项目文件夹拖到本文件上，或直接双击（默认用上一级目录）
set "P=%~1"
if "%P%"=="" set "P=%~dp0.."
echo 项目：%P%
python "%~dp0..\scripts\hx.py" translate "%P%\2_json_jp" "%P%\3_json_cn"
if errorlevel 1 (
  echo.
  echo 运行出错。先确认：1) 装了 Python  2) 填好 scripts\config.json 的 api_key
  pause
)
pause
