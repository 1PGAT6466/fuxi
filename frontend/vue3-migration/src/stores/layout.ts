/**
 * 伏羲 v2.1 — 布局状态管理 (Pinia Store)
 *
 * 管理布局方案的响应式状态：
 * - 布局列表
 * - 当前激活的布局
 * - 保存/激活/删除操作
 * - 导入/导出状态
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { LayoutPlan, LayoutListResponse, DisplayConfiguration } from '@/types/layout';
import layoutService from '@/services/layout-store/LayoutService';

export const useLayoutStore = defineStore('layout', () => {
  // ========== State ==========

  /** 布局方案列表 */
  const layouts = ref<LayoutPlan[]>([]);

  /** 当前激活的布局 ID */
  const activeLayoutId = ref<string | null>(null);

  /** 是否正在加载 */
  const isLoading = ref(false);

  /** 错误信息 */
  const error = ref<string | null>(null);

  /** 当前显示器配置 */
  const displayConfiguration = ref<DisplayConfiguration>(
    layoutService.detectDisplayConfiguration(),
  );

  // ========== Getters ==========

  /** 当前激活的布局方案 */
  const activeLayout = computed<LayoutPlan | null>(() => {
    if (!activeLayoutId.value) return null;
    return layouts.value.find((l) => l.id === activeLayoutId.value) || null;
  });

  /** 所有非默认布局 */
  const customLayouts = computed<LayoutPlan[]>(() => {
    return layouts.value.filter((l) => !l.isDefault);
  });

  /** 默认布局 */
  const defaultLayout = computed<LayoutPlan | null>(() => {
    return layouts.value.find((l) => l.isDefault) || null;
  });

  // ========== Actions ==========

  /**
   * 加载布局列表
   */
  async function loadLayouts(): Promise<LayoutListResponse> {
    isLoading.value = true;
    error.value = null;

    try {
      const result = await layoutService.listLayouts();
      layouts.value = result.layouts.sort(
        (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime(),
      );
      activeLayoutId.value = result.activeLayoutId;
      return result;
    } catch (err: any) {
      error.value = err?.message || '加载布局列表失败';
      return { layouts: [], total: 0, activeLayoutId: null };
    } finally {
      isLoading.value = false;
    }
  }

  /**
   * 保存当前布局
   */
  async function saveLayout(
    name: string,
    windows: Parameters<typeof layoutService.saveLayout>[1],
    options?: Parameters<typeof layoutService.saveLayout>[2],
  ) {
    isLoading.value = true;
    error.value = null;

    try {
      const result = await layoutService.saveLayout(name, windows, options);
      if (result.success && result.layout) {
        // 更新本地列表
        const idx = layouts.value.findIndex((l) => l.id === result.layout!.id);
        if (idx >= 0) {
          layouts.value[idx] = result.layout;
        } else {
          layouts.value.unshift(result.layout);
        }
        if (options?.setActive) {
          activeLayoutId.value = result.layout.id;
        }
      }
      return result;
    } catch (err: any) {
      error.value = err?.message || '保存布局失败';
      return { success: false, message: error.value };
    } finally {
      isLoading.value = false;
    }
  }

  /**
   * 激活布局方案
   */
  async function activateLayout(layoutId: string) {
    isLoading.value = true;
    error.value = null;

    try {
      const result = await layoutService.activateLayout(layoutId);
      if (result.success) {
        activeLayoutId.value = layoutId;
      }
      return result;
    } catch (err: any) {
      error.value = err?.message || '激活布局失败';
      return { success: false, snapshots: [], message: error.value };
    } finally {
      isLoading.value = false;
    }
  }

  /**
   * 删除布局方案
   */
  async function deleteLayout(layoutId: string) {
    isLoading.value = true;
    error.value = null;

    try {
      const result = await layoutService.deleteLayout(layoutId);
      if (result.success) {
        layouts.value = layouts.value.filter((l) => l.id !== layoutId);
        if (activeLayoutId.value === layoutId) {
          activeLayoutId.value = null;
        }
      }
      return result;
    } catch (err: any) {
      error.value = err?.message || '删除布局失败';
      return { success: false, message: error.value };
    } finally {
      isLoading.value = false;
    }
  }

  /**
   * 导出所有布局
   */
  async function exportLayouts() {
    try {
      return await layoutService.exportLayouts();
    } catch (err: any) {
      error.value = err?.message || '导出布局失败';
      return null;
    }
  }

  /**
   * 导入布局
   */
  async function importLayouts(jsonData: string, overwrite: boolean = false) {
    isLoading.value = true;
    error.value = null;

    try {
      const result = await layoutService.importLayouts(jsonData, overwrite);
      if (result.success) {
        await loadLayouts(); // 重新加载列表
      }
      return result;
    } catch (err: any) {
      error.value = err?.message || '导入布局失败';
      return { success: false, message: error.value };
    } finally {
      isLoading.value = false;
    }
  }

  /**
   * 刷新显示器配置
   */
  function refreshDisplayConfiguration() {
    displayConfiguration.value = layoutService.detectDisplayConfiguration();
  }

  /**
   * 检查布局是否兼容当前显示器
   */
  function isLayoutCompatible(layoutId: string): boolean {
    const layout = layouts.value.find((l) => l.id === layoutId);
    if (!layout) return false;
    return layoutService.isLayoutCompatible(layout, displayConfiguration.value.fingerprint);
  }

  return {
    // state
    layouts,
    activeLayoutId,
    isLoading,
    error,
    displayConfiguration,

    // getters
    activeLayout,
    customLayouts,
    defaultLayout,

    // actions
    loadLayouts,
    saveLayout,
    activateLayout,
    deleteLayout,
    exportLayouts,
    importLayouts,
    refreshDisplayConfiguration,
    isLayoutCompatible,
  };
});
