@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
rem 用法：把项目文件夹拖到本文件上，或直接双击（默认用上一级目录）
set "P=%~1"
if "%P%"=="" set "P=%~dp0.."
if exist "%~dp0..\tools\汉化待办.exe" (
  "%~dp0..\tools\汉化待办.exe" "%P%"
) else (
  python "%~dp0..\scripts\todo_gui.py" "%P%"
)
