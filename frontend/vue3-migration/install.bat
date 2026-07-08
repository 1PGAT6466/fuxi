@echo off
echo 伏羲体系 Vue 3 迁移安装脚本
echo ================================
echo.

echo 检查 Node.js 版本...
node --version
if errorlevel 1 (
    echo 错误: 未找到 Node.js，请先安装 Node.js 16+
    pause
    exit /b 1
)

echo.
echo 检查 npm 版本...
npm --version
if errorlevel 1 (
    echo 错误: 未找到 npm
    pause
    exit /b 1
)

echo.
echo 安装项目依赖...
npm install
if errorlevel 1 (
    echo 错误: 依赖安装失败
    pause
    exit /b 1
)

echo.
echo 安装完成！
echo.
echo 下一步:
echo 1. 运行 npm run dev 启动开发服务器
echo 2. 访问 http://localhost:3000 查看应用
echo.
pause