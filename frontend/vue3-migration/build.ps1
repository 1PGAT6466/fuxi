# 伏羲体系 Vue 3 构建脚本
Write-Host "伏羲体系 Vue 3 构建脚本" -ForegroundColor Green
Write-Host "========================" -ForegroundColor Green
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

Write-Host "构建生产版本..." -ForegroundColor Yellow
npm run build

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "构建成功！" -ForegroundColor Green
    Write-Host "输出目录: dist/" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "下一步:" -ForegroundColor Yellow
    Write-Host "1. 运行 npm run preview 预览构建结果" -ForegroundColor Cyan
    Write-Host "2. 运行 deploy.ps1 部署到服务器" -ForegroundColor Cyan
} else {
    Write-Host ""
    Write-Host "构建失败！" -ForegroundColor Red
    exit 1
}