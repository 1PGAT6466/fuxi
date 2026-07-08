# 伏羲体系 Vue 3 测试脚本
Write-Host "伏羲体系 Vue 3 测试脚本" -ForegroundColor Green
Write-Host "========================" -ForegroundColor Green
Write-Host ""

# 运行迁移测试
Write-Host "运行迁移测试..." -ForegroundColor Yellow
node test-migration.js

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "测试完成！" -ForegroundColor Green
    Write-Host ""
    Write-Host "下一步:" -ForegroundColor Yellow
    Write-Host "1. 运行 dev.ps1 启动开发服务器" -ForegroundColor Cyan
    Write-Host "2. 运行 build.ps1 构建生产版本" -ForegroundColor Cyan
} else {
    Write-Host ""
    Write-Host "测试失败！" -ForegroundColor Red
    exit 1
}