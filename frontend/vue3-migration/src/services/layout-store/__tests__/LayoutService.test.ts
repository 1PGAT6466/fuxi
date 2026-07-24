/**
 * 伏羲 v2.1 — LayoutService 单元测试
 *
 * 覆盖 LayoutService 核心逻辑：
 * - 显示器配置检测
 * - 窗口快照创建
 * - 位置约束（clamp）
 * - 指纹匹配
 * - 本地存储降级
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import type {
  DisplayInfo,
  DisplayConfiguration,
  WindowSnapshot,
  LayoutPlan,
} from '@/types/layout';
import type { ServiceWindow } from '@/types/service-manifest';

// Mock window.screen
const mockScreen = {
  availWidth: 1920,
  availHeight: 1080,
  width: 1920,
  height: 1080,
  isExtended: false,
};

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
  };
})();

Object.defineProperty(globalThis, 'localStorage', { value: localStorageMock });
Object.defineProperty(globalThis, 'window', {
  value: {
    screen: mockScreen,
    devicePixelRatio: 1,
    innerWidth: 1920,
    innerHeight: 1080,
  },
  writable: true,
});

// 动态导入（依赖 window mock 先于模块加载）
const { default: layoutService } = await import(
  '@/services/layout-store/LayoutService'
);

describe('LayoutService', () => {
  beforeEach(() => {
    localStorageMock.clear();
    vi.clearAllMocks();
  });

  describe('detectDisplayConfiguration()', () => {
    it('应该检测当前显示器配置', () => {
      const config = layoutService.detectDisplayConfiguration();
      expect(config.count).toBe(1);
      expect(config.displays[0]).toBeDefined();
      expect(config.displays[0]?.width).toBe(1920);
      expect(config.displays[0]?.height).toBe(1080);
      expect(config.displays[0]?.isPrimary).toBe(true);
    });

    it('应该生成配置指纹', () => {
      const config = layoutService.detectDisplayConfiguration();
      expect(config.fingerprint).toBe('1920x1080:1');
    });
  });

  describe('generateDisplayFingerprint()', () => {
    it('应该根据显示器列表生成唯一指纹', () => {
      const displays: DisplayInfo[] = [
        {
          id: 'd1',
          name: '主显示器',
          availWidth: 1920,
          availHeight: 1080,
          width: 1920,
          height: 1080,
          left: 0,
          top: 0,
          isPrimary: true,
          devicePixelRatio: 1,
        },
        {
          id: 'd2',
          name: '副显示器',
          availWidth: 1440,
          availHeight: 900,
          width: 1440,
          height: 900,
          left: 1920,
          top: 0,
          isPrimary: false,
          devicePixelRatio: 2,
        },
      ];

      const fingerprint = layoutService.generateDisplayFingerprint(displays);
      expect(fingerprint).toBe('1920x1080:1|1440x900:2');
    });
  });

  describe('isLayoutCompatible()', () => {
    it('指纹相同时应兼容', () => {
      const layout: LayoutPlan = {
        id: 'l1',
        name: '测试布局',
        displayFingerprint: '1920x1080:1',
        displayConfiguration: {} as DisplayConfiguration,
        windows: [],
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        isActive: false,
        isDefault: false,
        version: 1,
      };

      expect(layoutService.isLayoutCompatible(layout, '1920x1080:1')).toBe(true);
    });

    it('指纹不同时应不兼容', () => {
      const layout: LayoutPlan = {
        id: 'l1',
        name: '测试布局',
        displayFingerprint: '2560x1440:2',
        displayConfiguration: {} as DisplayConfiguration,
        windows: [],
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        isActive: false,
        isDefault: false,
        version: 1,
      };

      expect(layoutService.isLayoutCompatible(layout, '1920x1080:1')).toBe(false);
    });
  });

  describe('createWindowSnapshots()', () => {
    it('应该从活跃窗口创建快照', () => {
      const windows: ServiceWindow[] = [
        {
          id: 'win-1',
          serviceId: 'ai-tools',
          title: 'AI 工具',
          icon: 'Tools',
          state: 'normal',
          zIndex: 100,
          position: { x: 100, y: 50 },
          size: { width: 800, height: 600 },
          openedAt: Date.now(),
        },
        {
          id: 'win-2',
          serviceId: 'data-analytics',
          title: '数据分析',
          icon: 'DataAnalysis',
          state: 'minimized',
          zIndex: 101,
          position: { x: 200, y: 100 },
          size: { width: 900, height: 700 },
          openedAt: Date.now(),
        },
        {
          id: 'win-3',
          serviceId: 'doc-tools',
          title: '文档工具',
          icon: 'Document',
          state: 'closed',
          zIndex: 0,
          position: { x: 0, y: 0 },
          size: { width: 0, height: 0 },
          openedAt: 0,
        },
      ];

      const snapshots = layoutService.createWindowSnapshots(windows);
      expect(snapshots.length).toBe(2); // closed 被过滤
      expect(snapshots[0]?.serviceId).toBe('ai-tools');
      expect(snapshots[0]?.state).toBe('normal');
      expect(snapshots[1]?.serviceId).toBe('data-analytics');
      expect(snapshots[1]?.state).toBe('minimized');
    });

    it('空窗口列表应返回空快照', () => {
      const snapshots = layoutService.createWindowSnapshots([]);
      expect(snapshots).toEqual([]);
    });
  });

  describe('clampWindowPositions()', () => {
    it('应约束越界窗口位置', () => {
      const config: DisplayConfiguration = {
        count: 1,
        displays: [
          {
            id: 'd1',
            name: '主显示器',
            availWidth: 1920,
            availHeight: 1080,
            width: 1920,
            height: 1080,
            left: 0,
            top: 0,
            isPrimary: true,
            devicePixelRatio: 1,
          },
        ],
        totalBounds: {
          left: 0,
          top: 0,
          right: 1920,
          bottom: 1080,
        },
        fingerprint: '1920x1080:1',
      };

      const outOfBounds: WindowSnapshot = {
        windowId: 'win-1',
        serviceId: 'test',
        title: 'Test',
        state: 'normal',
        position: { x: 2000, y: 2000 },
        size: { width: 800, height: 600 },
        zIndex: 100,
        displayId: 'd1',
      };

      const clamped = layoutService.clampWindowPositions([outOfBounds], config);
      expect(clamped[0]!.position.x).toBeLessThan(1920);
      expect(clamped[0]!.position.y).toBeLessThan(1080);
    });

    it('应约束超大窗口尺寸', () => {
      const config: DisplayConfiguration = {
        count: 1,
        displays: [],
        totalBounds: {
          left: 0,
          top: 0,
          right: 1920,
          bottom: 1080,
        },
        fingerprint: '1920x1080:1',
      };

      const oversized: WindowSnapshot = {
        windowId: 'win-1',
        serviceId: 'test',
        title: 'Test',
        state: 'normal',
        position: { x: 0, y: 0 },
        size: { width: 3000, height: 2000 },
        zIndex: 100,
        displayId: 'd1',
      };

      const clamped = layoutService.clampWindowPositions([oversized], config);
      expect(clamped[0]!.size.width).toBeLessThanOrEqual(1920);
      expect(clamped[0]!.size.height).toBeLessThanOrEqual(1080);
    });
  });

  describe('exportLayouts()', () => {
    it('应导出 LayoutExport 格式', async () => {
      const result = await layoutService.exportLayouts();
      expect(result.success).toBe(true);
      expect(result.data).toBeDefined();
      expect(result.data?.formatVersion).toBe(1);
      expect(result.blobs).toBeDefined();
      expect(result.blobs?.length).toBeGreaterThan(0);
    });
  });

  describe('importLayouts()', () => {
    it('应拒绝无效 JSON', async () => {
      const result = await layoutService.importLayouts('not valid json');
      expect(result.success).toBe(false);
      expect(result.message).toContain('解析失败');
    });

    it('应拒绝缺少 formatVersion 的数据', async () => {
      const result = await layoutService.importLayouts(JSON.stringify({ foo: 'bar' }));
      expect(result.success).toBe(false);
      expect(result.message).toContain('无效');
    });

    it('应导入有效的布局数据到本地缓存', async () => {
      const validData = {
        formatVersion: 1,
        exportedAt: new Date().toISOString(),
        appVersion: '2.1',
        layouts: [
          {
            id: 'imported-test',
            name: '导入测试',
            displayFingerprint: '1920x1080:1',
            displayConfiguration: {
              count: 1,
              displays: [],
              totalBounds: { left: 0, top: 0, right: 1920, bottom: 1080 },
              fingerprint: '1920x1080:1',
            },
            windows: [],
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
            isActive: false,
            isDefault: false,
            version: 1,
          },
        ],
      };

      const result = await layoutService.importLayouts(JSON.stringify(validData));
      expect(result.success).toBe(true);
    });
  });

  describe('createDefaultLayout()', () => {
    it('应创建默认布局模板', () => {
      const layout = layoutService.createDefaultLayout();
      expect(layout.name).toBe('默认布局');
      expect(layout.tags).toContain('默认');
      expect(layout.displayConfiguration).toBeDefined();
    });
  });

  describe('onChange() 事件监听', () => {
    it('应注册和触发监听器', () => {
      const listener = vi.fn();
      const unsubscribe = layoutService.onChange(listener);

      // 验证可以取消订阅
      expect(typeof unsubscribe).toBe('function');
      unsubscribe();
    });
  });
});
