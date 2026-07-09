@echo off
REM 伏羲 v1.44 - 启动脚本（包含任务队列）
REM 使用方法: scripts\start_with_queue.bat

echo === 伏羲 v1.44 启动脚本 ===
echo 包含 Redis Stream 任务队列支持
echo.

REM 检查 Redis 是否运行
echo 1. 检查 Redis 服务...
redis-cli ping >nul 2>&1
if %errorlevel% neq 0 (
    echo    Redis 未运行，请先启动 Redis 服务
    echo    下载地址: https://redis.io/download
    pause
    exit /b 1
) else (
    echo    ✓ Redis 已运行
)

REM 检查环境变量
echo 2. 检查环境变量...
if "%FUXI_JWT_SECRET%"=="" (
    if exist ".env" (
        echo    从 .env 文件加载环境变量...
        for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
            if not "%%a"=="" if not "%%a"=="#" set "%%a=%%b"
        )
    )
)

if "%FUXI_JWT_SECRET%"=="" (
    echo    ✗ FUXI_JWT_SECRET 未设置
    echo    请在 .env 文件中设置 FUXI_JWT_SECRET
    pause
    exit /b 1
)
echo    ✓ 环境变量检查通过

REM 检查 Python 依赖
echo 3. 检查 Python 依赖...
python -c "import redis" >nul 2>&1
if %errorlevel% neq 0 (
    echo    安装 redis Python 库...
    pip install redis>=5.0.0
)
echo    ✓ Python 依赖检查通过

REM 启动伏羲服务器
echo 4. 启动伏羲服务器...
echo    服务器将在 http://0.0.0.0:8080 启动
echo    任务队列将自动初始化
echo.
echo    API 端点:
echo    - 文件上传: POST /api/upload
echo    - 任务状态: GET /api/tasks/{task_id}
echo    - 评测任务: POST /api/evaluation
echo.
echo    按 Ctrl+C 停止服务器
echo.

python -m src.server