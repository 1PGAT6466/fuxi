/**
 * 跨窗口剪贴板服务 单元测试
 *
 * 测试范围：
 * - ClipboardService 核心逻辑（复制/粘贴/历史管理）
 * - 格式转换
 * - 收藏管理
 * - LRU 裁剪
 * - 跨窗口广播
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { ClipboardService, getClipboardService, destroyClipboardService } from '@/services/clipboard/service';
import type { ClipboardEntry, ClipboardContentFormat } from '@/services/clipboard/types';

// Mock navigator.clipboard
const mockClipboardText = vi.hoisted(() => {
  let text = '';
  return {
    getText: () => text,
    setText: (t: string) => { text = t; },
    reset: () => { text = ''; },
  };
});

Object.defineProperty(navigator, 'clipboard', {
  value: {
    readText: vi.fn(async () => mockClipboardText.getText()),
    writeText: vi.fn(async (t: string) => {
      mockClipboardText.setText(t);
    }),
  },
  writable: true,
  configurable: true,
});

// Mock BroadcastChannel
const mockBC = vi.hoisted(() => ({
  postMessage: vi.fn(),
  close: vi.fn(),
  onmessage: null as ((ev: MessageEvent) => void) | null,
}));

vi.stubGlobal('BroadcastChannel', vi.fn(function () {
  mockBC.postMessage = vi.fn();
  mockBC.close = vi.fn();
  mockBC.onmessage = null;
  return mockBC;
}));

// Mock API
vi.mock('@/api/clipboard', () => ({
  syncClipboard: vi.fn().mockResolvedValue({ success: true, entryId: 'server-123', totalCount: 1 }),
  getClipboardHistory: vi.fn().mockResolvedValue({ entries: [], total: 0, cached: 0 }),
  deleteClipboardEntry: vi.fn().mockResolvedValue({ success: true }),
  toggleClipboardFavorite: vi.fn().mockResolvedValue({ success: true }),
  clearClipboardHistory: vi.fn().mockResolvedValue({ success: true }),
  batchDeleteClipboardEntries: vi.fn().mockResolvedValue({ success: true, affectedCount: 3 }),
}));

describe('ClipboardService', () => {
  let service: ClipboardService;

  beforeEach(async () => {
    mockClipboardText.reset();
    destroyClipboardService();
    service = new ClipboardService('test-window');
    await service.initialize();
  });

  afterEach(() => {
    service.destroy();
    vi.clearAllMocks();
  });

  // ═══════════════════════════════════════════
  // 初始化
  // ═══════════════════════════════════════════

  describe('initialize', () => {
    it('应该正确初始化服务', () => {
      const status = service.getStatus();
      expect(status.initialized).toBe(true);
      expect(status.historyCount).toBe(0);
    });

    it('重复初始化应该被跳过', async () => {
      await service.initialize();
      const status = service.getStatus();
      expect(status.initialized).toBe(true);
    });
  });

  // ═══════════════════════════════════════════
  // 复制
  // ═══════════════════════════════════════════

  describe('copy', () => {
    it('应该复制文本并添加到历史', async () => {
      const entry = await service.copy('Hello World');
      expect(entry).not.toBeNull();
      expect(entry!.plainText).toBe('Hello World');
      expect(entry!.format).toBe('text');

      const history = service.getHistory();
      expect(history.length).toBe(1);
    });

    it('应该写入系统剪贴板', async () => {
      await service.copy('System Copy Test');
      expect(mockClipboardText.getText()).toBe('System Copy Test');
    });

    it('应该支持指定格式', async () => {
      const entry = await service.copy('{"key":"value"}', 'json');
      expect(entry!.format).toBe('json');
    });

    it('5秒内重复内容不应重复添加', async () => {
      const entry1 = await service.copy('Duplicate');
      const entry2 = await service.copy('Duplicate');
      const history = service.getHistory();

      expect(history.length).toBe(1);
      expect(entry2!.id).toBe(entry1!.id); // 返回同一个条目
    });

    it('应该按时间倒序排列（最新在前）', async () => {
      await service.copy('First');
      await service.copy('Second');
      await service.copy('Third');

      const history = service.getHistory();
      expect(history[0].plainText).toBe('Third');
      expect(history[1].plainText).toBe('Second');
      expect(history[2].plainText).toBe('First');
    });
  });

  // ═══════════════════════════════════════════
  // 粘贴
  // ═══════════════════════════════════════════

  describe('paste', () => {
    it('无历史时应该返回 null', async () => {
      const content = await service.paste();
      expect(content).toBeNull();
    });

    it('应该返回最新条目的内容', async () => {
      await service.copy('Paste test content');
      const content = await service.paste();
      expect(content).toBe('Paste test content');
    });

    it('应该支持指定条目粘贴', async () => {
      const entry1 = await service.copy('Entry One');
      const entry2 = await service.copy('Entry Two');

      const content = await service.paste(entry1!.id);
      expect(content).toBe('Entry One');
    });
  });

  // ═══════════════════════════════════════════
  // 历史管理
  // ═══════════════════════════════════════════

  describe('history management', () => {
    it('应该正确获取历史', async () => {
      await service.copy('A');
      await service.copy('B');
      await service.copy('C');

      const history = service.getHistory();
      expect(history.length).toBe(3);
    });

    it('删除条目后应该移除', async () => {
      const entry = await service.copy('Delete me');
      const historyBefore = service.getHistory().length;
      service.deleteEntry(entry!.id);
      const historyAfter = service.getHistory().length;

      expect(historyAfter).toBe(historyBefore - 1);
      expect(service.getHistory().find(e => e.id === entry!.id)).toBeUndefined();
    });

    it('清空历史应该移除所有条目', async () => {
      await service.copy('A');
      await service.copy('B');
      await service.copy('C');

      service.clearHistory();
      expect(service.getHistory().length).toBe(0);
    });

    it('超过最大历史条目时应裁剪（LRU）', async () => {
      // 默认 maxHistorySize = 100
      for (let i = 0; i < 105; i++) {
        await service.copy(`Item ${i}`);
      }

      const history = service.getHistory();
      expect(history.length).toBeLessThanOrEqual(100);
      // 最旧的一条应该已被裁掉
      expect(history[history.length - 1].plainText).toBe('Item 5');
    });

    it('搜索历史应该正确过滤', () => {
      // 直接使用内部方法测试（无需 async copy）
      service['history'] = [
        {
          id: '1', format: 'text', plainText: 'Apple pie recipe',
          isFavorite: false, createdAt: new Date().toISOString(),
        },
        {
          id: '2', format: 'text', plainText: 'Banana smoothie',
          isFavorite: false, createdAt: new Date().toISOString(),
        },
        {
          id: '3', format: 'text', plainText: 'Apple juice',
          isFavorite: false, createdAt: new Date().toISOString(),
        },
      ] as ClipboardEntry[];

      const results = service.searchHistory('apple');
      expect(results.length).toBe(2);
      expect(results[0].plainText).toContain('Apple');
    });
  });

  // ═══════════════════════════════════════════
  // 收藏管理
  // ═══════════════════════════════════════════

  describe('favorites', () => {
    it('默认条目不应收藏', async () => {
      const entry = await service.copy('Not favorited');
      expect(service.isFavorite(entry!.id)).toBe(false);
    });

    it('可以收藏条目', async () => {
      const entry = await service.copy('Favorite me');
      service.toggleFavorite(entry!.id);

      expect(service.isFavorite(entry!.id)).toBe(true);
      expect(service.getFavorites().length).toBe(1);
    });

    it('可以取消收藏', async () => {
      const entry = await service.copy('Unfavorite');
      service.toggleFavorite(entry!.id); // 收藏
      expect(service.isFavorite(entry!.id)).toBe(true);

      service.toggleFavorite(entry!.id); // 取消收藏
      expect(service.isFavorite(entry!.id)).toBe(false);
      expect(service.getFavorites().length).toBe(0);
    });

    it('不存在的条目 toggleFavorite 返回 false', () => {
      const result = service.toggleFavorite('non-existent-id');
      expect(result).toBe(false);
    });
  });

  // ═══════════════════════════════════════════
  // 格式转换
  // ═══════════════════════════════════════════

  describe('format conversion', () => {
    it('相同格式转换应该返回原文', () => {
      const result = service.convertFormat('hello', 'text', 'text');
      expect(result).toBe('hello');
    });

    it('text → html 应该包装为 <p> 标签', () => {
      const result = service.convertFormat('Hello\nWorld', 'text', 'html');
      expect(result).toContain('<p>Hello</p>');
      expect(result).toContain('<p>World</p>');
    });

    it('html → text 应该去除标签', () => {
      const result = service.convertFormat('<p>Hello <b>World</b></p>', 'html', 'text');
      expect(result).toBe('Hello World');
    });

    it('text → json 应该尝试解析', () => {
      const result = service.convertFormat('{"key":"value"}', 'text', 'json');
      const parsed = JSON.parse(result);
      expect(parsed.key).toBe('value');
    });

    it('无效的 json 转换应该回退', () => {
      const result = service.convertFormat('not json', 'text', 'json');
      const parsed = JSON.parse(result);
      expect(parsed.text).toBe('not json');
    });

    it('可以注册自定义转换器', () => {
      const beforeCount = service.getConverters().length;
      service.registerConverter({
        from: 'text',
        to: 'json',
        priority: 10,
        convert: (content: string) => JSON.stringify({ custom: content }),
      });

      expect(service.getConverters().length).toBe(beforeCount + 1);
    });
  });

  // ═══════════════════════════════════════════
  // 跨窗口广播
  // ═══════════════════════════════════════════

  describe('cross-window sync', () => {
    it('复制时应该广播到其他窗口', async () => {
      await service.copy('Broadcast test');
      expect(mockBC.postMessage).toHaveBeenCalled();
    });

    it('删除时应该广播', async () => {
      const entry = await service.copy('To delete');
      mockBC.postMessage.mockClear();
      service.deleteEntry(entry!.id);
      expect(mockBC.postMessage).toHaveBeenCalled();
    });
  });

  // ═══════════════════════════════════════════
  // 事件系统
  // ═══════════════════════════════════════════

  describe('event system', () => {
    it('监听器应该收到变更事件', async () => {
      const listener = vi.fn();
      const unsubscribe = service.on('change', listener);

      await service.copy('Event test');
      expect(listener).toHaveBeenCalled();
      expect(listener.mock.calls[0][0].action).toBe('copied');

      unsubscribe();
    });

    it('取消订阅后不应收到事件', async () => {
      const listener = vi.fn();
      const unsubscribe = service.on('change', listener);
      unsubscribe();

      await service.copy('No event');
      expect(listener).not.toHaveBeenCalled();
    });
  });

  // ═══════════════════════════════════════════
  // 全局单例
  // ═══════════════════════════════════════════

  describe('global singleton', () => {
    it('getClipboardService 应该返回同一个实例', () => {
      const s1 = getClipboardService('win-1');
      const s2 = getClipboardService('win-2');
      expect(s1).toBe(s2);
    });

    it('destroyClipboardService 应该清空实例', () => {
      const s1 = getClipboardService('win-1');
      destroyClipboardService();
      const s2 = getClipboardService('win-2');
      expect(s1).not.toBe(s2);
    });
  });

  // ═══════════════════════════════════════════
  // 边界情况
  // ═══════════════════════════════════════════

  describe('edge cases', () => {
    it('空内容复制应该支持', async () => {
      const entry = await service.copy('');
      expect(entry).not.toBeNull();
      expect(entry!.plainText).toBe('');
    });

    it('非常长内容应该可以处理', async () => {
      const longText = 'A'.repeat(100000);
      const entry = await service.copy(longText);
      expect(entry).not.toBeNull();
      expect(entry!.plainText).toBe(longText);
    });

    it('包含特殊字符的内容应该可以处理', async () => {
      const special = '<script>alert("xss")</script>\n\t特殊字符：中文🀄emoji🎉';
      const entry = await service.copy(special);
      expect(entry!.plainText).toBe(special);
    });

    it('大量复制后应该保持稳定', async () => {
      for (let i = 0; i < 200; i++) {
        await service.copy(`Item ${i}`);
      }

      const status = service.getStatus();
      expect(status.historyCount).toBeLessThanOrEqual(100);
    });
  });
});
