/**
 * 伏羲 v2.1 — Feature Flags Store (Pinia)
 *
 * 功能：
 * - 管理 BONUS 服务的开关状态 + 后端 Feature Flag 同步
 * - 与后端 /api/feature-flags 保持一致
 * - localStorage 持久化
 *
 * v2.1 统一 flag key 集合（以后端 DEFAULT_FLAGS 为准）：
 *   前端本地 flag（enable_* 前缀，控制服务可见性）：
 *     - enable_data_analytics  → 数据分析工作台
 *     - enable_doc_tools       → 文档工具集
 *     - enable_dxf_viewer      → DXF 工程浏览器
 *   后端同步 flag（从 /api/feature-flags 拉取）：
 *     - 核心 flag: shaoyang_sag_extract, taiyang_multi_hop, taiyang_seed_score
 *     - SAG 管线: taiyang_sag_pipeline, taiyang_path_a, taiyang_event_search, taiyang_sql_multi_hop
 *     - 增强 flag: enhanced_pipeline
 *     - 基础 flag: graphrag_multi_hop, query_planner, table_structured_search 等
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { getFeatureFlags as fetchBackendFlags } from '@/api/featureFlags';

const FLAGS_STORAGE_KEY = 'fuxi-feature-flags';

/** 从 localStorage 加载开关状态 */
function loadFlags(): Record<string, boolean> {
  try {
    const saved = localStorage.getItem(FLAGS_STORAGE_KEY);
    if (saved) {
      return JSON.parse(saved);
    }
  } catch {
    // localStorage 不可用或格式错误
  }
  return {};
}

export const useFeatureFlags = defineStore('featureFlags', () => {
  // ============================================
  // State — 前端本地开关
  // ============================================

  const savedFlags = loadFlags();

  const enableDataAnalytics = ref<boolean>(savedFlags.enable_data_analytics ?? false);
  const enableDocTools = ref<boolean>(savedFlags.enable_doc_tools ?? false);
  const enableDxfViewer = ref<boolean>(savedFlags.enable_dxf_viewer ?? false);

  // ============================================
  // State — 后端同步开关（从 /api/feature-flags 拉取）
  // ============================================

  const backendFlags = ref<Record<string, boolean>>({});
  const backendDefaults = ref<Record<string, boolean>>({});
  const flagsLoaded = ref<boolean>(false);

  // ============================================
  // Getters
  // ============================================

  /** 本地开关 */
  const localFlags = computed(() => ({
    enable_data_analytics: enableDataAnalytics.value,
    enable_doc_tools: enableDocTools.value,
    enable_dxf_viewer: enableDxfViewer.value,
  }));

  /** 所有开关（本地 + 后端合并） */
  const allFlags = computed(() => ({
    ...backendFlags.value,
    ...localFlags.value,
  }));

  /** 后端某个 flag 是否开启 */
  const isEnabled = (key: string): boolean => {
    // 先查本地
    if (key.startsWith('enable_')) {
      return localFlags.value[key as keyof typeof localFlags.value] ?? false;
    }
    // 再查后端
    return backendFlags.value[key] ?? false;
  };

  // ============================================
  // Actions — 本地开关
  // ============================================

  /** 设置单个本地开关 */
  function setLocalFlag(key: string, value: boolean): void {
    switch (key) {
      case 'enable_data_analytics':
        enableDataAnalytics.value = value;
        break;
      case 'enable_doc_tools':
        enableDocTools.value = value;
        break;
      case 'enable_dxf_viewer':
        enableDxfViewer.value = value;
        break;
      default:
        console.warn(`[featureFlags] 未知本地开关: ${key}`);
        return;
    }
    persist();
  }

  /** 批量设置本地开关 */
  function setLocalFlags(flags: Record<string, boolean>): void {
    for (const [key, value] of Object.entries(flags)) {
      setLocalFlag(key, value);
    }
  }

  // ============================================
  // Actions — 后端同步
  // ============================================

  /** 从后端拉取 Feature Flag 列表 */
  async function loadBackendFlags(): Promise<void> {
    try {
      const data: any = await fetchBackendFlags();
      if (data.flags) {
        backendFlags.value = data.flags;
      }
      if (data.defaults) {
        backendDefaults.value = data.defaults;
      }
      flagsLoaded.value = true;
    } catch (err) {
      console.warn('[featureFlags] 拉取后端开关失败', err);
      // 网络错误时使用上次缓存值
    }
  }

  /** 更新后端开关 */
  async function updateBackendFlag(key: string, value: boolean): Promise<void> {
    const { updateFeatureFlag } = await import('@/api/featureFlags');
    await updateFeatureFlag(key, value);
    // 乐观更新本地缓存
    backendFlags.value = { ...backendFlags.value, [key]: value };
  }

  // ============================================
  // Actions — 兼容旧版 setFlag / setFlags
  // ============================================

  /** @deprecated 使用 setLocalFlag 替代 */
  function setFlag(key: string, value: boolean): void {
    console.warn(
      '[featureFlags] setFlag 已废弃，请使用 setLocalFlag（前端开关）或 updateBackendFlag（后端开关）',
    );
    setLocalFlag(key, value);
  }

  /** @deprecated 使用 setLocalFlags 替代 */
  function setFlags(flags: Record<string, boolean>): void {
    setLocalFlags(flags);
  }

  // ============================================
  // 持久化
  // ============================================

  function persist(): void {
    try {
      localStorage.setItem(
        FLAGS_STORAGE_KEY,
        JSON.stringify({
          enable_data_analytics: enableDataAnalytics.value,
          enable_doc_tools: enableDocTools.value,
          enable_dxf_viewer: enableDxfViewer.value,
        }),
      );
    } catch {
      // localStorage 不可用
    }
  }

  return {
    // State — 本地
    enableDataAnalytics,
    enableDocTools,
    enableDxfViewer,
    // State — 后端
    backendFlags,
    backendDefaults,
    flagsLoaded,
    // Getters
    localFlags,
    allFlags,
    isEnabled,
    // Actions — 本地
    setLocalFlag,
    setLocalFlags,
    // Actions — 后端
    loadBackendFlags,
    updateBackendFlag,
    // Actions — 兼容旧版
    setFlag,
    setFlags,
  };
});
