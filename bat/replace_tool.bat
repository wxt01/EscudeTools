@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
rem 用法：把项目文件夹拖到本文件上，或直接双击
set "P=%~1"
if "%P%"=="" set "P=%~dp0.."
cd /d "%~dp0..\scripts"
echo 译文目录：%P%\3_json_cn
echo.
python "%~dp0..\scripts\replace_tool.py" "%P%"
pause
