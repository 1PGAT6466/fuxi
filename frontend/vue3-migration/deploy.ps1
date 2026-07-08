# 伏羲体系 Vue 3 部署脚本
Write-Host "伏羲体系 Vue 3 部署脚本" -ForegroundColor Green
Write-Host "========================" -ForegroundColor Green
Write-Host ""

# 检查是否已构建
if (-not (Test-Path "dist")) {
    Write-Host "错误: 未找到 dist 目录，请先运行 npm run build" -ForegroundColor Red
    exit 1
}

# 部署到服务器
Write-Host "部署到服务器..." -ForegroundColor Yellow
$server = "feng-shaoxuan@172.25.30.200"
$remotePath = "/path/to/伏羲-v1.44/repo/frontend/"

Write-Host "服务器: $server" -ForegroundColor Cyan
Write-Host "远程路径: $remotePath" -ForegroundColor Cyan
Write-Host ""

# 使用 scp 复制文件
Write-Host "复制文件到服务器..." -ForegroundColor Yellow
scp -r dist/* "${server}:${remotePath}"

if ($LASTEXITCODE -eq 0) {
    Write-Host "部署成功！" -ForegroundColor Green
    Write-Host ""
    Write-Host "访问地址: http://172.25.30.200" -ForegroundColor Cyan
} else {
    Write-Host "部署失败！" -ForegroundColor Red
    exit 1
}