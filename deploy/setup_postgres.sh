#!/bin/bash
# ============================================================================
# 伏羲 RAG 4.0 — PostgreSQL + pgvector 部署脚本
# 目标服务器: 172.25.30.200 (PGAT-storge)
# ============================================================================

set -e

# ======== 安全修复 (CWE-798): 从环境变量读取凭证 ========
if [ -z "$FUXI_PG_PASSWORD" ]; then
    echo "❌ 错误: FUXI_PG_PASSWORD 环境变量未设置！"
    echo "   请设置: export FUXI_PG_PASSWORD='<强密码>'"
    echo "   示例: export FUXI_PG_PASSWORD='d8K2@pL9!qR5mX1#vF7'"
    exit 1
fi

PG_PASSWORD="$FUXI_PG_PASSWORD"
PG_USER="${FUXI_PG_USER:-feng-shaoxuan}"
PG_DATABASE="${FUXI_PG_DATABASE:-fuxi}"

echo "============================================"
echo "伏羲 PostgreSQL + pgvector 部署"
echo "============================================"

# 1. 安装 PostgreSQL
if ! command -v psql &> /dev/null; then
    echo "[1/5] 安装 PostgreSQL..."
    sudo apt-get update
    sudo apt-get install -y postgresql postgresql-client postgresql-contrib
    echo "✅ PostgreSQL 安装完成"
else
    echo "[1/5] ✅ PostgreSQL 已安装: $(psql --version)"
fi

# 2. 安装 pgvector 扩展
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_available_extensions WHERE name='vector'" 2>/dev/null | grep -q 1; then
    echo "[2/5] 编译安装 pgvector..."
    
    PG_VERSION=$(psql --version | grep -oP '\d+' | head -1)
    PG_CONFIG="/usr/bin/pg_config"
    
    # 安装构建依赖
    sudo apt-get install -y build-essential postgresql-server-dev-${PG_VERSION} git
    
    # 克隆并编译
    TMP_DIR=$(mktemp -d)
    cd "$TMP_DIR"
    git clone --branch v0.8.0 https://github.com/pgvector/pgvector.git
    cd pgvector
    make
    sudo make install
    
    cd /
    rm -rf "$TMP_DIR"
    echo "✅ pgvector 编译安装完成"
else
    echo "[2/5] ✅ pgvector 已安装"
fi

# 3. 创建数据库和用户
echo "[3/5] 创建数据库..."
sudo -u postgres psql <<EOF
-- 创建用户（如果不存在）
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$PG_USER') THEN
        CREATE ROLE "$PG_USER" WITH LOGIN PASSWORD '$PG_PASSWORD';
    END IF;
END
\$\$;

-- 创建数据库
SELECT 'CREATE DATABASE $PG_DATABASE OWNER "$PG_USER"'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$PG_DATABASE')\gexec

-- 授权
GRANT ALL PRIVILEGES ON DATABASE $PG_DATABASE TO "$PG_USER";
EOF
echo "✅ 数据库创建完成"

# 4. 启用扩展
echo "[4/5] 启用扩展..."
sudo -u postgres psql -d fuxi <<'EOF'
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
EOF
echo "✅ 扩展启用完成"

# 5. 导入 Schema
echo "[5/5] 导入 Schema..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PGPASSWORD="$PG_PASSWORD" psql -h localhost -U "$PG_USER" -d "$PG_DATABASE" -f "$SCRIPT_DIR/schema_pg.sql"
echo "✅ Schema 导入完成"

echo ""
echo "============================================"
echo "部署完成！"
echo "数据库: $PG_DATABASE @ localhost:5432"
echo "用户: $PG_USER"
echo "连接测试:"
echo "  PGPASSWORD=\$FUXI_PG_PASSWORD psql -h localhost -U $PG_USER -d $PG_DATABASE -c '\\dt'"
echo "============================================"
