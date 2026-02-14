# OpenAkita 完整包构建脚本 (Windows PowerShell)
# 输出: 包含全部依赖和模型的安装包 (~1GB)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$SetupCenterDir = Join-Path $ProjectRoot "apps\setup-center"
$ResourceDir = Join-Path $SetupCenterDir "src-tauri\resources"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  OpenAkita 完整包构建" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# Step 1: 打包 Python 后端 (完整模式)
Write-Host "`n[1/4] 打包 Python 后端 (full mode)..." -ForegroundColor Yellow
python "$ScriptDir\build_backend.py" --mode full
if ($LASTEXITCODE -ne 0) { throw "Python 后端打包失败" }

# Step 2: 预打包可选模块
Write-Host "`n[2/4] 预打包可选模块..." -ForegroundColor Yellow
python "$ScriptDir\bundle_modules.py"
if ($LASTEXITCODE -ne 0) { throw "模块预打包失败" }

# Step 3: 复制到 Tauri resources
Write-Host "`n[3/4] 复制后端和模块到 Tauri resources..." -ForegroundColor Yellow
$DistServerDir = Join-Path $ProjectRoot "dist\openakita-server"
$ModulesDir = Join-Path $ScriptDir "modules"
$TargetServerDir = Join-Path $ResourceDir "openakita-server"
$TargetModulesDir = Join-Path $ResourceDir "modules"

if (Test-Path $TargetServerDir) { Remove-Item -Recurse -Force $TargetServerDir }
if (Test-Path $TargetModulesDir) { Remove-Item -Recurse -Force $TargetModulesDir }
New-Item -ItemType Directory -Force -Path $ResourceDir | Out-Null
Copy-Item -Recurse $DistServerDir $TargetServerDir
if (Test-Path $ModulesDir) {
    Copy-Item -Recurse $ModulesDir $TargetModulesDir
}
Write-Host "  后端: $TargetServerDir"
Write-Host "  模块: $TargetModulesDir"

# Step 4: 构建 Tauri 应用（通过 TAURI_CONFIG 追加 modules 资源）
Write-Host "`n[4/4] 构建 Tauri 应用..." -ForegroundColor Yellow
Push-Location $SetupCenterDir
try {
    # 完整包需要额外包含 modules 资源目录
    $env:TAURI_CONFIG = '{"bundle":{"resources":["resources/openakita-server/","resources/modules/"]}}'
    npx tauri build
    if ($LASTEXITCODE -ne 0) { throw "Tauri 构建失败" }
} finally {
    $env:TAURI_CONFIG = $null
    Pop-Location
}

Write-Host "`n============================================" -ForegroundColor Green
Write-Host "  完整包构建完成!" -ForegroundColor Green
Write-Host "  安装包位于: $SetupCenterDir\src-tauri\target\release\bundle\" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
