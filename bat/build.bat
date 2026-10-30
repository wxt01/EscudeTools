@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
rem 用法：把项目文件夹拖到本文件上
set "P=%~1"
if "%P%"=="" set "P=%~dp0.."
echo 项目：%P%
echo.
echo 1 = 全量构建（含字库，约 4 分钟）
echo 2 = 只重打脚本（改译文后用，约 1 分钟）
set /p MODE=选择 [1/2]:
if "%MODE%"=="2" (
  python "%~dp0..\scripts\build.py" --project "%P%" --no-gfx
) else (
  python "%~dp0..\scripts\build.py" --project "%P%"
)
if errorlevel 1 (
  echo.
  echo 构建失败，往上翻看报错。
)
pause
