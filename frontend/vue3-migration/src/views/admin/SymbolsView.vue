<template>
  <!--
    伏羲 v2.1 — 四象系统状态
    四象卡片布局：少阳(消化)/太阳(探索)/少阴(判断)/太阴(守护)
    每个卡片内显示关联器官网格 + 健康状态指示 + 2×2 响应式布局
  -->
  <div class="symbols-view">
    <h2 class="page-title">四象系统状态</h2>
    <p class="page-desc">监测四象模块运行状态与关联能力映射</p>

    <!-- 四象卡片：2×2 布局 -->
    <div class="symbols-grid">
      <div
        v-for="symbol in symbols"
        :key="symbol.id"
        class="symbol-card"
        :class="`symbol-card--${symbol.cssClass}`"
      >
        <div class="symbol-card-header">
          <div class="symbol-icon">
            <el-icon :size="28">
              <component :is="symbol.icon" />
            </el-icon>
          </div>
          <div class="symbol-title">
            <h3>{{ symbol.name }}</h3>
            <span class="symbol-subtitle">{{ symbol.subtitle }}（{{ symbol.role }}）</span>
          </div>
        </div>

        <div class="symbol-status">
          <span
            class="status-indicator"
            :class="`status-indicator--${symbol.health}`"
          />
          <span class="status-label">{{ healthLabel(symbol.health) }}</span>
        </div>

        <!-- 关联器官网格 -->
        <div class="organ-grid">
          <div
            v-for="organ in symbol.organs"
            :key="organ.name"
            class="organ-item"
            :class="`organ-item--${organ.status}`"
          >
            <span class="organ-name">{{ organ.name }}</span>
            <span class="organ-desc">{{ organ.desc }}</span>
            <el-tag :type="organTagType(organ.status)" size="small">
              {{ organStatusLabel(organ.status) }}
            </el-tag>
          </div>
        </div>

        <div class="symbol-footer">
          <span class="footer-metric">
            活跃度：<strong>{{ symbol.activity }}%</strong>
          </span>
          <span class="footer-metric">
            任务：<strong>{{ symbol.taskCount }}</strong>
          </span>
        </div>
      </div>
    </div>

    <!-- 加载态 -->
    <div v-if="loading" class="symbols-loading">
      <el-skeleton :rows="8" animated />
    </div>

    <!-- 空状态 -->
    <div v-else-if="symbols.length === 0 && !loading" class="symbols-empty">
      <el-empty description="暂无四象数据" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { Sunny, Moon, Sunrise, Sunset, Loading } from '@element-plus/icons-vue';
import apiClient from '@/api';

// ─── 类型 ───
interface OrganInfo {
  name: string;
  desc: string;
  status: 'healthy' | 'warning' | 'critical';
}

interface SymbolData {
  id: string;
  name: string;
  subtitle: string;
  role: string;
  icon: unknown;
  cssClass: string;
  health: 'healthy' | 'warning' | 'critical';
  activity: number;
  taskCount: number;
  organs: OrganInfo[];
}

// ─── 状态 ───
const loading = ref(false);
const symbols = ref<SymbolData[]>([]);

// ─── Mock 数据 ───
function getMockSymbols(): SymbolData[] {
  return [
    {
      id: 'shaoyang',
      name: '少阳',
      subtitle: '初生之阳',
      role: '消化',
      icon: Sunrise,
      cssClass: 'shaoyang',
      health: 'healthy',
      activity: 82,
      taskCount: 34,
      organs: [
        { name: '文档解析', desc: 'PDF/Word 提取', status: 'healthy' },
        { name: '文本分块', desc: '智能分句', status: 'healthy' },
        { name: '实体提取', desc: 'NER 识别', status: 'healthy' },
        { name: '语义编码', desc: '向量化', status: 'warning' },
      ],
    },
    {
      id: 'taiyang',
      name: '太阳',
      subtitle: '盛阳之光',
      role: '探索',
      icon: Sunny,
      cssClass: 'taiyang',
      health: 'healthy',
      activity: 95,
      taskCount: 67,
      organs: [
        { name: '知识检索', desc: '向量搜索', status: 'healthy' },
        { name: '联网搜索', desc: '实时查询', status: 'healthy' },
        { name: '图谱遍历', desc: '关系探索', status: 'healthy' },
        { name: '假设生成', desc: '推理路径', status: 'healthy' },
      ],
    },
    {
      id: 'shaoyin',
      name: '少阴',
      subtitle: '初生之阴',
      role: '判断',
      icon: Sunset,
      cssClass: 'shaoyin',
      health: 'warning',
      activity: 65,
      taskCount: 21,
      organs: [
        { name: '结果验证', desc: '事实核查', status: 'healthy' },
        { name: '一致性检验', desc: '逻辑审查', status: 'warning' },
        { name: '质量评分', desc: '置信度评估', status: 'warning' },
        { name: '偏见检测', desc: '公平性分析', status: 'critical' },
      ],
    },
    {
      id: 'taiyin',
      name: '太阴',
      subtitle: '盛阴之藏',
      role: '守护',
      icon: Moon,
      cssClass: 'taiyin',
      health: 'healthy',
      activity: 78,
      taskCount: 45,
      organs: [
        { name: '数据存储', desc: '持久化', status: 'healthy' },
        { name: '备份恢复', desc: '容灾', status: 'healthy' },
        { name: '安全审计', desc: '日志追踪', status: 'healthy' },
        { name: '资源管理', desc: '内存/磁盘', status: 'warning' },
      ],
    },
  ];
}

// ─── 方法 ───
function healthLabel(health: string): string {
  const map: Record<string, string> = {
    healthy: '健康',
    warning: '注意',
    critical: '异常',
  };
  return map[health] || health;
}

function organTagType(status: string): 'success' | 'warning' | 'danger' {
  const map: Record<string, 'success' | 'warning' | 'danger'> = {
    healthy: 'success',
    warning: 'warning',
    critical: 'danger',
  };
  return map[status] || 'warning';
}

function organStatusLabel(status: string): string {
  const map: Record<string, string> = {
    healthy: '正常',
    warning: '注意',
    critical: '异常',
  };
  return map[status] || status;
}

// ─── 数据加载 ───
async function fetchSymbols(): Promise<void> {
  loading.value = true;
  try {
    const data = (await apiClient.get('/api/symbols/status')) as Record<string, unknown>;
    symbols.value = (data.symbols || data.data || []) as SymbolData[];
  } catch {
    console.warn('[SymbolsView] API 不可用，使用 mock 数据');
    symbols.value = getMockSymbols();
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  fetchSymbols();
});
</script>

<style scoped lang="scss">
.symbols-view {
  max-width: 1200px;
  margin: 0 auto;
  padding: 28px 24px;
}

.page-title {
  margin: 0 0 8px;
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
}

.page-desc {
  margin: 0 0 24px;
  font-size: var(--font-size-caption);
  color: var(--text-secondary);
}

/* ─── 四象卡片 2×2 网格 ─── */
.symbols-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}

.symbol-card {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  padding: 24px;
  border-top: 4px solid transparent;
  transition:
    transform var(--duration-normal) var(--ease-out),
    box-shadow var(--duration-normal) var(--ease-out);

  &:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
  }

  &--shaoyang {
    border-top-color: #FF6700; // 暖橙 — 少阳
  }
  &--taiyang {
    border-top-color: #E74C3C; // 红 — 太阳
  }
  &--shaoyin {
    border-top-color: #3A6B8C; // 蓝 — 少阴
  }
  &--taiyin {
    border-top-color: #4A7C59; // 绿 — 太阴
  }
}

/* ─── 卡片头部 ─── */
.symbol-card-header {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 16px;
}

.symbol-icon {
  width: 52px;
  height: 52px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;

  .symbol-card--shaoyang & {
    background: rgba(255, 103, 0, 0.1);
    color: #FF6700;
  }
  .symbol-card--taiyang & {
    background: rgba(231, 76, 60, 0.1);
    color: #E74C3C;
  }
  .symbol-card--shaoyin & {
    background: rgba(58, 107, 140, 0.1);
    color: #3A6B8C;
  }
  .symbol-card--taiyin & {
    background: rgba(74, 124, 89, 0.1);
    color: #4A7C59;
  }
}

.symbol-title {
  h3 {
    margin: 0;
    font-size: 20px;
    font-weight: 700;
    color: var(--text-primary);
  }

  .symbol-subtitle {
    font-size: 12px;
    color: var(--text-tertiary);
  }
}

/* ─── 健康状态 ─── */
.symbol-status {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  padding: 8px 12px;
  background: var(--bg-subtle);
  border-radius: var(--radius-sm);
}

.status-indicator {
  width: 10px;
  height: 10px;
  border-radius: 50%;

  &--healthy {
    background: #34C759;
    box-shadow: 0 0 6px rgba(52, 199, 89, 0.4);
  }
  &--warning {
    background: #FF9500;
    box-shadow: 0 0 6px rgba(255, 149, 0, 0.4);
  }
  &--critical {
    background: #FF3B30;
    box-shadow: 0 0 6px rgba(255, 59, 48, 0.4);
  }
}

.status-label {
  font-size: var(--font-size-caption);
  font-weight: 600;
  color: var(--text-primary);
}

/* ─── 关联器官网格 ─── */
.organ-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  margin-bottom: 16px;
}

.organ-item {
  padding: 10px;
  border-radius: var(--radius-sm);
  background: var(--bg-subtle);
  border-left: 3px solid transparent;

  &--healthy {
    border-left-color: #34C759;
  }
  &--warning {
    border-left-color: #FF9500;
  }
  &--critical {
    border-left-color: #FF3B30;
  }
}

.organ-name {
  display: block;
  font-size: var(--font-size-caption);
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 2px;
}

.organ-desc {
  display: block;
  font-size: 11px;
  color: var(--text-tertiary);
  margin-bottom: 6px;
}

/* ─── 卡片底部指标 ─── */
.symbol-footer {
  display: flex;
  gap: 24px;
  padding-top: 12px;
  border-top: 1px solid var(--bg-divider);
}

.footer-metric {
  font-size: var(--font-size-small);
  color: var(--text-secondary);

  strong {
    color: var(--text-primary);
    font-weight: 700;
  }
}

/* ─── 加载 / 空状态 ─── */
.symbols-loading {
  margin-top: 24px;
  padding: 24px;
  background: var(--bg-card);
  border-radius: var(--radius-md);
}

.symbols-empty {
  margin-top: 24px;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: 40px;
}

/* ─── 响应式 ─── */
@media (max-width: 1023px) {
  .symbols-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 767px) {
  .symbols-view {
    padding: 16px;
  }

  .organ-grid {
    grid-template-columns: 1fr;
  }
}
</style>
