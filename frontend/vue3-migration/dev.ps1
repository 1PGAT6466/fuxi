# 伏羲体系 Vue 3 开发服务器启动脚本
Write-Host "伏羲体系 Vue 3 开发服务器" -ForegroundColor Green
Write-Host "=========================" -ForegroundColor Green
Write-Host ""

# 检查依赖是否安装
if (-not (Test-Path "node_modules")) {
    Write-Host "依赖未安装，正在安装..." -ForegroundColor Yellow
    npm install
    if ($LASTEXITCODE -ne 0) {
        Write-Host "错误: 依赖安装失败" -ForegroundColor Red
        exit 1
    }
}

Write-Host "启动开发服务器..." -ForegroundColor Yellow
Write-Host ""
Write-Host "访问地址: http://localhost:3000" -ForegroundColor Cyan
Write-Host "按 Ctrl+C 停止服务器" -ForegroundColor Yellow
Write-Host ""

npm run dev