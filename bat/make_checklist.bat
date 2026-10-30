@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
rem 用法：把项目文件夹拖到本文件上，或直接双击
set "P=%~1"
if "%P%"=="" set "P=%~dp0.."
python "%~dp0..\scripts\make_checklist.py" "%P%"
pause
