#!/bin/bash
# 伏羲 v1.44 - 启动脚本（包含任务队列）
# 使用方法: ./scripts/start_with_queue.sh

set -e

echo "=== 伏羲 v1.44 启动脚本 ==="
echo "包含 Redis Stream 任务队列支持"
echo ""

# 检查 Redis 是否运行
echo "1. 检查 Redis 服务..."
if ! redis-cli ping > /dev/null 2>&1; then
    echo "   Redis 未运行，正在启动..."
    # 尝试启动 Redis
    if command -v redis-server &> /dev/null; then
        redis-server --daemonize yes
        sleep 2
        if redis-cli ping > /dev/null 2>&1; then
            echo "   ✓ Redis 启动成功"
        else
            echo "   ✗ Redis 启动失败"
            exit 1
        fi
    else
        echo "   ✗ Redis 未安装"
        echo "   请安装 Redis: https://redis.io/download"
        exit 1
    fi
else
    echo "   ✓ Redis 已运行"
fi

# 检查环境变量
echo "2. 检查环境变量..."
if [ -z "$FUXI_JWT_SECRET" ]; then
    if [ -f ".env" ]; then
        echo "   从 .env 文件加载环境变量..."
        export $(grep -v '^#' .env | xargs)
    fi
fi

if [ -z "$FUXI_JWT_SECRET" ]; then
    echo "   ✗ FUXI_JWT_SECRET 未设置"
    echo "   请在 .env 文件中设置 FUXI_JWT_SECRET"
    exit 1
fi
echo "   ✓ 环境变量检查通过"

# 检查 Python 依赖
echo "3. 检查 Python 依赖..."
if ! python -c "import redis" > /dev/null 2>&1; then
    echo "   安装 redis Python 库..."
    pip install redis>=5.0.0
fi
echo "   ✓ Python 依赖检查通过"

# 启动伏羲服务器
echo "4. 启动伏羲服务器..."
echo "   服务器将在 http://0.0.0.0:8080 启动"
echo "   任务队列将自动初始化"
echo ""
echo "   API 端点:"
echo "   - 文件上传: POST /api/upload"
echo "   - 任务状态: GET /api/tasks/{task_id}"
echo "   - 评测任务: POST /api/evaluation"
echo ""
echo "   按 Ctrl+C 停止服务器"
echo ""

python -m src.server