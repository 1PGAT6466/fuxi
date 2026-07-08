#!/usr/bin/env bash
# ============================================================
# 伏羲 v1.50 Phase C · Dream Cycle Cron 调度配置
# ============================================================
# 功能：注册 EasyClaw cron 任务，每夜 02:00 自动运行消化循环
# 使用：在项目根目录执行: bash scripts/cron-dream-cycle.sh
# ============================================================

set -e

CRON_NAME="伏羲·夜梦"
CRON_SCHEDULE="0 2 * * *"
PROJECT_ROOT="E:/easyclaw/伏羲-v1.44/repo"
PYTHON_CMD="python -c \"import asyncio; import sys; sys.path.insert(0, '${PROJECT_ROOT}/src'); from evolution.dream_cycle import DreamCycle; asyncio.run(DreamCycle().run())\""

echo "============================================"
echo "  伏羲 v1.50 Phase C · Dream Cycle Cron"
echo "============================================"
echo ""
echo "  任务名称: ${CRON_NAME}"
echo "  调度规则: ${CRON_SCHEDULE} (每夜 02:00)"
echo "  项目路径: ${PROJECT_ROOT}"
echo ""

# 使用 EasyClaw cron add 注册任务
easyclaw cron add \
  --name "${CRON_NAME}" \
  --schedule "${CRON_SCHEDULE}" \
  --session isolated \
  --command "${PYTHON_CMD}"

echo ""
echo "✅ Cron 任务已注册"
echo ""
echo "查看任务: easyclaw cron list"
echo "编辑任务: easyclaw cron edit <id>"
echo "删除任务: easyclaw cron rm <id>"
echo ""

# 可选：立即手动执行一次
read -p "是否立即手动执行一次 Dream Cycle? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "正在执行 Dream Cycle..."
    curl -s -X POST "http://localhost:8080/api/evolution/dream-cycle/run" | python -m json.tool
fi
