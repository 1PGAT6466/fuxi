/**
 * 伏羲 v2.1 — 运维 Store
 * 插件源管理 + 监控中心状态管理
 *
 * 功能：
 * - 缓存 API 数据，减少重复请求
 * - 自动刷新（30秒间隔）
 * - 统一错误处理
 */
import { defineStore } from 'pinia';
import { ref, shallowRef, computed } from 'vue';
import type {
  PluginSource,
  SyncHistory,
  SystemMetrics,
  AggregatedMetrics,
  Alert,
  AlertRule,
  HealthCheckResult,
} from '@/api/ops';
import {
  getPluginSources,
  triggerPluginSync,
  testPluginConnection,
  addPluginSource,
  updatePluginSource,
  deletePluginSource,
  getSyncHistory,
  getSystemMetrics,
  getAggregatedMetrics,
  getAlerts,
  getAlertRules,
  getOpsHealth,
} from '@/api/ops';
import { ElMessage } from 'element-plus';
import { createLogger } from '@/utils/logger';

const logger = createLogger('OpsStore');

/** 自动刷新间隔（毫秒） */
const REFRESH_INTERVAL = 30_000;

export const useOpsStore = defineStore('ops', () => {
  // ============================
  // 插件源状态
  // ============================
  const pluginSources = shallowRef<PluginSource[]>([]);
  const syncHistory = shallowRef<SyncHistory[]>([]);
  const pluginLoading = ref(false);
  const pluginError = ref<string | null>(null);

  // ============================
  // 监控指标状态
  // ============================
  const metrics = ref<SystemMetrics | null>(null);
  const aggregatedMetrics = ref<AggregatedMetrics | null>(null);
  const metricsLoading = ref(false);
  const metricsError = ref<string | null>(null);

  // ============================
  // 告警状态
  // ============================
  const alerts = shallowRef<Alert[]>([]);
  const alertRules = shallowRef<AlertRule[]>([]);
  const alertsLoading = ref(false);

  // ============================
  // 健康检查状态
  // ============================
  const health = ref<HealthCheckResult | null>(null);
  const healthLoading = ref(false);

  // ============================
  // 自动刷新控制
  // ============================
  let refreshTimer: ReturnType<typeof setInterval> | null = null;
  const autoRefreshEnabled = ref(false);

  // ============================
  // 计算属性
  // ============================

  /** 未解决的告警数 */
  const unresolvedAlertsCount = computed(() => alerts.value.filter(a => !a.resolved).length);

  /** 严重告警数 */
  const criticalAlertsCount = computed(() =>
    alerts.value.filter(a => !a.resolved && a.level === 'critical').length,
  );

  /** 活跃插件源数 */
  const activePluginCount = computed(() =>
    pluginSources.value.filter(p => p.status === 'active').length,
  );

  /** 系统健康状态文字 */
  const healthStatus = computed(() => {
    if (!health.value) return '未知';
    switch (health.value.status) {
      case 'healthy': return '正常';
      case 'degraded': return '降级';
      case 'unhealthy': return '异常';
      default: return '未知';
    }
  });

  // ============================
  // 插件源 Actions
  // ============================

  /** 加载插件源列表 */
  async function fetchPluginSources(): Promise<void> {
    pluginLoading.value = true;
    pluginError.value = null;
    try {
      pluginSources.value = await getPluginSources();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '获取插件源失败';
      pluginError.value = msg;
      logger.error('获取插件源失败:', err);
    } finally {
      pluginLoading.value = false;
    }
  }

  /** 加载同步历史 */
  async function fetchSyncHistory(): Promise<void> {
    try {
      syncHistory.value = await getSyncHistory();
    } catch (err) {
      logger.error('获取同步历史失败:', err);
    }
  }

  /** 触发同步 */
  async function triggerSync(sourceId: string): Promise<boolean> {
    try {
      const result = await triggerPluginSync(sourceId);
      if (result.success) {
        ElMessage.success('同步已触发');
        await fetchPluginSources();
        await fetchSyncHistory();
        return true;
      }
      ElMessage.warning(result.message);
      return false;
    } catch (err) {
      ElMessage.error('触发同步失败');
      logger.error('触发同步失败:', err);
      return false;
    }
  }

  /** 测试连接 */
  async function testConnection(sourceId: string): Promise<boolean> {
    try {
      const result = await testPluginConnection(sourceId);
      if (result.success) {
        ElMessage.success(`连接成功，延迟 ${result.latency}ms`);
        return true;
      }
      ElMessage.warning(result.message);
      return false;
    } catch (err) {
      ElMessage.error('测试连接失败');
      logger.error('测试连接失败:', err);
      return false;
    }
  }

  /** 添加插件源 */
  async function createPluginSource(data: Omit<PluginSource, 'id' | 'status' | 'lastSync'>): Promise<boolean> {
    try {
      await addPluginSource(data);
      ElMessage.success('插件源添加成功');
      await fetchPluginSources();
      return true;
    } catch (err) {
      ElMessage.error('添加插件源失败');
      logger.error('添加插件源失败:', err);
      return false;
    }
  }

  /** 更新插件源 */
  async function modifyPluginSource(id: string, data: Partial<PluginSource>): Promise<boolean> {
    try {
      await updatePluginSource(id, data);
      ElMessage.success('插件源更新成功');
      await fetchPluginSources();
      return true;
    } catch (err) {
      ElMessage.error('更新插件源失败');
      logger.error('更新插件源失败:', err);
      return false;
    }
  }

  /** 删除插件源 */
  async function removePluginSource(id: string): Promise<boolean> {
    try {
      await deletePluginSource(id);
      ElMessage.success('插件源已删除');
      await fetchPluginSources();
      return true;
    } catch (err) {
      ElMessage.error('删除插件源失败');
      logger.error('删除插件源失败:', err);
      return false;
    }
  }

  // ============================
  // 监控指标 Actions
  // ============================

  /** 加载实时指标 */
  async function fetchMetrics(): Promise<void> {
    metricsLoading.value = true;
    metricsError.value = null;
    try {
      metrics.value = await getSystemMetrics();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '获取指标失败';
      metricsError.value = msg;
      logger.error('获取指标失败:', err);
    } finally {
      metricsLoading.value = false;
    }
  }

  /** 加载聚合指标（趋势） */
  async function fetchAggregatedMetrics(range = '1h'): Promise<void> {
    try {
      aggregatedMetrics.value = await getAggregatedMetrics({ range });
    } catch (err) {
      logger.error('获取聚合指标失败:', err);
    }
  }

  // ============================
  // 告警 Actions
  // ============================

  /** 加载告警历史 */
  async function fetchAlerts(): Promise<void> {
    alertsLoading.value = true;
    try {
      alerts.value = await getAlerts({ limit: 100 });
    } catch (err) {
      logger.error('获取告警失败:', err);
    } finally {
      alertsLoading.value = false;
    }
  }

  /** 加载告警规则 */
  async function fetchAlertRules(): Promise<void> {
    try {
      alertRules.value = await getAlertRules();
    } catch (err) {
      logger.error('获取告警规则失败:', err);
    }
  }

  // ============================
  // 健康检查 Actions
  // ============================

  /** 加载健康检查 */
  async function fetchHealth(): Promise<void> {
    healthLoading.value = true;
    try {
      health.value = await getOpsHealth();
    } catch (err) {
      logger.error('获取健康检查失败:', err);
    } finally {
      healthLoading.value = false;
    }
  }

  // ============================
  // 批量加载 + 自动刷新
  // ============================

  /** 加载所有监控数据 */
  async function fetchAllMonitoring(): Promise<void> {
    await Promise.allSettled([
      fetchMetrics(),
      fetchAggregatedMetrics(),
      fetchAlerts(),
      fetchAlertRules(),
      fetchHealth(),
    ]);
  }

  /** 加载所有插件源数据 */
  async function fetchAllPlugins(): Promise<void> {
    await Promise.allSettled([
      fetchPluginSources(),
      fetchSyncHistory(),
    ]);
  }

  /** 启动自动刷新 */
  function startAutoRefresh(): void {
    if (refreshTimer) return;
    autoRefreshEnabled.value = true;
    refreshTimer = setInterval(() => {
      fetchAllMonitoring();
    }, REFRESH_INTERVAL);
    logger.info('自动刷新已启动，间隔', REFRESH_INTERVAL / 1000, '秒');
  }

  /** 停止自动刷新 */
  function stopAutoRefresh(): void {
    if (refreshTimer) {
      clearInterval(refreshTimer);
      refreshTimer = null;
    }
    autoRefreshEnabled.value = false;
    logger.info('自动刷新已停止');
  }

  // ============================
  // 清理
  // ============================
  function $reset(): void {
    stopAutoRefresh();
    pluginSources.value = [];
    syncHistory.value = [];
    metrics.value = null;
    aggregatedMetrics.value = null;
    alerts.value = [];
    alertRules.value = [];
    health.value = null;
    pluginError.value = null;
    metricsError.value = null;
  }

  return {
    // 插件源状态
    pluginSources,
    syncHistory,
    pluginLoading,
    pluginError,

    // 监控指标状态
    metrics,
    aggregatedMetrics,
    metricsLoading,
    metricsError,

    // 告警状态
    alerts,
    alertRules,
    alertsLoading,

    // 健康检查状态
    health,
    healthLoading,

    // 自动刷新
    autoRefreshEnabled,

    // 计算属性
    unresolvedAlertsCount,
    criticalAlertsCount,
    activePluginCount,
    healthStatus,

    // 插件源 Actions
    fetchPluginSources,
    fetchSyncHistory,
    triggerSync,
    testConnection,
    createPluginSource,
    modifyPluginSource,
    removePluginSource,

    // 监控 Actions
    fetchMetrics,
    fetchAggregatedMetrics,
    fetchAlerts,
    fetchAlertRules,
    fetchHealth,

    // 批量 + 刷新
    fetchAllMonitoring,
    fetchAllPlugins,
    startAutoRefresh,
    stopAutoRefresh,

    // 清理
    $reset,
  };
});
