# 伏羲体系 Vue 3 预览脚本
Write-Host "伏羲体系 Vue 3 预览脚本" -ForegroundColor Green
Write-Host "========================" -ForegroundColor Green
Write-Host ""

# 检查是否已构建
if (-not (Test-Path "dist")) {
    Write-Host "错误: 未找到 dist 目录，请先运行 build.ps1" -ForegroundColor Red
    exit 1
}

Write-Host "启动预览服务器..." -ForegroundColor Yellow
Write-Host ""
Write-Host "访问地址: http://localhost:4173" -ForegroundColor Cyan
Write-Host "按 Ctrl+C 停止服务器" -ForegroundColor Yellow
Write-Host ""

npm run preview