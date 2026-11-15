# publish.ps1 —— 打发布包
#
# 只带工具与文档：不含游戏数据、不含 API key、不含第三方二进制（engine\）。
# 用法：powershell -ExecutionPolicy Bypass -File 工具\publish.ps1
#       可选 -OutDir 指定输出目录（默认 主文件夹\10_发布）

param([string]$OutDir = "")

$ErrorActionPreference = "Stop"

$ToolRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Stamp    = Get-Date -Format "yyyyMMdd_HHmm"
if (-not $OutDir) { $OutDir = Join-Path (Split-Path -Parent $ToolRoot) "发布" }
if (-not (Test-Path -LiteralPath $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }

$Stage = Join-Path ([IO.Path]::GetTempPath()) ("escude_publish_" + $Stamp)
if (Test-Path -LiteralPath $Stage) { Remove-Item -LiteralPath $Stage -Recurse -Force }
New-Item -ItemType Directory -Path $Stage | Out-Null

# ---------- 1. 白名单复制 ----------
$WhitelistDirs  = @("scripts", "bat", "docs", "ui_image_toolkit", "vendor", "tools", "游戏")
$WhitelistFiles = @("README.md", "LICENSE", "project.example.json", "config.example.json",
                    ".gitignore", "ui_labels.example.json", "ui_misc.example.json")

foreach ($d in $WhitelistDirs) {
    $src = Join-Path $ToolRoot $d
    if (Test-Path -LiteralPath $src) {
        Copy-Item -LiteralPath $src -Destination $Stage -Recurse -Force
        Write-Output ("  收入目录: " + $d)
    }
}
foreach ($f in $WhitelistFiles) {
    $src = Join-Path $ToolRoot $f
    if (Test-Path -LiteralPath $src) {
        Copy-Item -LiteralPath $src -Destination $Stage -Force
        Write-Output ("  收入文件: " + $f)
    }
}
# 根目录下的 *.example.tsv 一并收入
Get-ChildItem -LiteralPath $ToolRoot -File -Filter "*.example.tsv" -ErrorAction SilentlyContinue |
    ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $Stage -Force; Write-Output ("  收入文件: " + $_.Name) }

# ---------- 2. 清掉不该发布的 ----------
$Junk = Get-ChildItem -LiteralPath $Stage -Recurse -Force -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -eq "_工作区" -or $_.Name -eq "__pycache__" -or $_.Name -eq "engine" -or
    $_.Name -eq "config.json" -or $_.Name -eq "project.json" -or
    $_.Extension -in @(".pyc", ".pyo", ".npy", ".bin", ".png", ".ttf", ".ttc", ".db", ".sqlite")
}
foreach ($j in $Junk) { if ($j.Exists) { Remove-Item -LiteralPath $j.FullName -Recurse -Force -ErrorAction SilentlyContinue } }

# ---------- 3. 安全检查 ----------
Write-Output ""
Write-Output "安全检查："
$Problems = 0
$TextFiles = Get-ChildItem -LiteralPath $Stage -Recurse -File -Force |
    Where-Object { $_.Extension -in @(".md", ".py", ".bat", ".json", ".tsv", ".ps1", ".txt", ".gitignore") -or $_.Name -eq ".gitignore" }

foreach ($t in $TextFiles) {
    $txt = [IO.File]::ReadAllText($t.FullName)
    if ($txt -match "sk-[A-Za-z0-9]{20,}") {
        Write-Output ("  [密钥] " + $t.FullName.Substring($Stage.Length))
        $Problems++
    }
    if ($txt -match '"api_key"\s*:\s*"[^"]+') {
        Write-Output ("  [api_key 非空] " + $t.FullName.Substring($Stage.Length))
        $Problems++
    }
    if ($txt -match "千艶万匣|戦巫|廃村少女") {
        Write-Output ("  [游戏名] " + $t.FullName.Substring($Stage.Length))
    }
}

# 预编译 exe 是否比源码旧
$Exe = Join-Path $Stage "tools\汉化待办.exe"
$Src = Join-Path $ToolRoot "scripts\todo_gui.py"
if ((Test-Path -LiteralPath $Exe) -and (Test-Path -LiteralPath $Src)) {
    if ((Get-Item -LiteralPath $Exe).LastWriteTime -lt (Get-Item -LiteralPath $Src).LastWriteTime) {
        Write-Output "  [提示] tools\汉化待办.exe 比 scripts\todo_gui.py 旧，建议重新 PyInstaller 打包"
    }
}

if ($Problems -gt 0) {
    Write-Output ""
    Write-Output "发现 $Problems 处敏感内容，已中止。修好后重跑。"
    Remove-Item -LiteralPath $Stage -Recurse -Force
    exit 1
}

# ---------- 4. 压缩与校验 ----------
$Zip = Join-Path $OutDir ("EscudeTools_" + $Stamp + ".zip")
Compress-Archive -Path (Join-Path $Stage "*") -DestinationPath $Zip -CompressionLevel Optimal -Force
Remove-Item -LiteralPath $Stage -Recurse -Force

$Hash = (Get-FileHash -LiteralPath $Zip -Algorithm SHA256).Hash
$Size = [math]::Round((Get-Item -LiteralPath $Zip).Length / 1MB, 2)
Set-Content -LiteralPath ($Zip + ".sha256") -Value ($Hash + "  " + (Split-Path -Leaf $Zip)) -Encoding utf8

Write-Output ""
Write-Output ("发布包: " + $Zip)
Write-Output ("大小:   " + $Size + " MB")
Write-Output ("sha256: " + $Hash)

