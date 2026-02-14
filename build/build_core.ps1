# OpenAkita 核心包构建脚本 (Windows PowerShell)
# 输出: 仅包含核心依赖的安装包 (~180MB)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$SetupCenterDir = Join-Path $ProjectRoot "apps\setup-center"
$ResourceDir = Join-Path $SetupCenterDir "src-tauri\resources"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  OpenAkita 核心包构建" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# Step 1: 打包 Python 后端 (核心模式)
Write-Host "`n[1/3] 打包 Python 后端 (core mode)..." -ForegroundColor Yellow
python "$ScriptDir\build_backend.py" --mode core
if ($LASTEXITCODE -ne 0) { throw "Python 后端打包失败" }

# Step 2: 复制打包结果到 Tauri resources
Write-Host "`n[2/3] 复制后端到 Tauri resources..." -ForegroundColor Yellow
$DistServerDir = Join-Path $ProjectRoot "dist\openakita-server"
$TargetDir = Join-Path $ResourceDir "openakita-server"

if (Test-Path $TargetDir) { Remove-Item -Recurse -Force $TargetDir }
New-Item -ItemType Directory -Force -Path $ResourceDir | Out-Null
Copy-Item -Recurse $DistServerDir $TargetDir
Write-Host "  已复制到: $TargetDir"

# Step 3: 构建 Tauri 应用
Write-Host "`n[3/3] 构建 Tauri 应用..." -ForegroundColor Yellow
Push-Location $SetupCenterDir
try {
    npm run tauri build
    if ($LASTEXITCODE -ne 0) { throw "Tauri 构建失败" }
} finally {
    Pop-Location
}

Write-Host "`n============================================" -ForegroundColor Green
Write-Host "  核心包构建完成!" -ForegroundColor Green
Write-Host "  安装包位于: $SetupCenterDir\src-tauri\target\release\bundle\" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
