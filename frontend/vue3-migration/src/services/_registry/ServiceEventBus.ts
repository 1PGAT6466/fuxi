/**
 * 伏羲 v2.1 — 服务事件总线
 *
 * 功能：
 * - emit/on/once/off 模式
 * - 命名空间隔离：service:{id}:{event}
 * - 支持通配符：service:*:click, service:ai-tools:*
 * - 支持全局事件：global:{event}
 *
 * 使用示例：
 *   bus.emit('service:ai-tools:complete', { result: 'ok' });
 *   bus.on('service:ai-tools:*', (payload) => { ... });
 *   bus.on('global:theme-changed', (theme) => { ... });
 *   bus.once('service:data-analytics:loaded', () => { ... });
 *   bus.off('service:ai-tools:complete');
 */

import type { EventHandler } from '@/types/service-manifest';

// ============================
// 通配符匹配工具
// ============================

/**
 * 将事件模式转换为正则，支持两种通配符：
 * - * 匹配单层（如 service:*:click 匹配 service:any:click）
 * - ** 匹配多层（如 service:** 匹配 service:any:sub:event）
 * - 不支持其他 glob 语法
 */
function globToRegex(pattern: string): RegExp {
  const escaped = pattern.replace(/[.+^${}()|[\]\\]/g, '\\$&');
  // ** 先替换为占位符，避免被 * 覆盖
  const doubleStarPlaceholder = '__DOUBLE_STAR__';
  const step1 = escaped.replace(/\\\*\\\*/g, doubleStarPlaceholder);
  const step2 = step1.replace(/\\\*/g, '[^:]+');
  const step3 = step2.replace(new RegExp(doubleStarPlaceholder, 'g'), '.*');
  return new RegExp(`^${step3}$`);
}

// ============================
// 事件总线实现
// ============================

class ServiceEventBus {
  /** 存储所有事件监听器：事件名 → 回调列表 */
  private listeners: Map<string, Set<EventHandler>> = new Map();

  /** 存储通配符模式监听器：正则 → 回调列表 */
  private patternListeners: Map<RegExp, Set<EventHandler>> = new Map();

  /** 存储一次性监听器（避免 off 时还需要匹配通配符） */
  private onceWrappers: WeakMap<EventHandler, EventHandler> = new WeakMap();

  /**
   * 发送事件
   *
   * @param event - 事件名（命名空间格式：service:{id}:{event} 或 global:{event}）
   * @param payload - 事件载荷
   */
  emit(event: string, ...payload: any[]): void {
    // 1. 精确匹配的监听器
    const exactListeners = this.listeners.get(event);
    if (exactListeners) {
      exactListeners.forEach((handler) => {
        try {
          handler(...payload);
        } catch (err) {
          console.error(`[ServiceEventBus] 事件处理器错误 "${event}":`, err);
        }
      });
    }

    // 2. 通配符匹配的监听器
    this.patternListeners.forEach((handlers, regex) => {
      if (regex.test(event)) {
        handlers.forEach((handler) => {
          try {
            handler(...payload);
          } catch (err) {
            console.error(`[ServiceEventBus] 通配符处理器错误 "${event}":`, err);
          }
        });
      }
    });
  }

  /**
   * 注册事件监听器
   *
   * @param event - 事件名或通配符模式
   * @param handler - 回调函数
   * @returns 取消监听的函数
   */
  on(event: string, handler: EventHandler): () => void {
    if (event.includes('*')) {
      // 通配符模式
      const regex = globToRegex(event);
      const handlers = this.patternListeners.get(regex) || new Set();
      handlers.add(handler);
      this.patternListeners.set(regex, handlers);

      return () => {
        const h = this.patternListeners.get(regex);
        if (h) {
          h.delete(handler);
          if (h.size === 0) {
            this.patternListeners.delete(regex);
          }
        }
      };
    }

    // 精确匹配
    const handlers = this.listeners.get(event) || new Set();
    handlers.add(handler);
    this.listeners.set(event, handlers);

    return () => {
      const h = this.listeners.get(event);
      if (h) {
        h.delete(handler);
        if (h.size === 0) {
          this.listeners.delete(event);
        }
      }
    };
  }

  /**
   * 注册一次性事件监听器
   *
   * @param event - 事件名或通配符模式
   * @param handler - 回调函数
   * @returns 取消监听的函数
   */
  once(event: string, handler: EventHandler): () => void {
    const wrapper: EventHandler = (...args: any[]) => {
      this.off(event, wrapper);
      handler(...args);
    };

    this.onceWrappers.set(handler, wrapper);

    if (event.includes('*')) {
      const regex = globToRegex(event);
      const handlers = this.patternListeners.get(regex) || new Set();
      handlers.add(wrapper);
      this.patternListeners.set(regex, handlers);

      return () => {
        const h = this.patternListeners.get(regex);
        if (h) {
          h.delete(wrapper);
          if (h.size === 0) {
            this.patternListeners.delete(regex);
          }
        }
      };
    }

    const handlers = this.listeners.get(event) || new Set();
    handlers.add(wrapper);
    this.listeners.set(event, handlers);

    return () => {
      const h = this.listeners.get(event);
      if (h) {
        h.delete(wrapper);
        if (h.size === 0) {
          this.listeners.delete(event);
        }
      }
    };
  }

  /**
   * 移除事件监听器
   *
   * @param event - 事件名或通配符模式
   * @param handler - 要移除的回调（可选，不传则移除该事件所有监听器）
   */
  off(event: string, handler?: EventHandler): void {
    if (!handler) {
      // 移除该事件/模式的所有监听器
      if (event.includes('*')) {
        const regex = globToRegex(event);
        // 找到匹配的正则并删除
        this.patternListeners.forEach((_handlers, key) => {
          if (key.source === regex.source) {
            this.patternListeners.delete(key);
          }
        });
      } else {
        this.listeners.delete(event);
      }
      return;
    }

    // 先检查 once 包装
    const onceWrapper = this.onceWrappers.get(handler);
    const targetHandler = onceWrapper || handler;

    if (event.includes('*')) {
      const regex = globToRegex(event);
      this.patternListeners.forEach((handlers, key) => {
        if (key.source === regex.source) {
          handlers.delete(targetHandler);
          if (handlers.size === 0) {
            this.patternListeners.delete(key);
          }
        }
      });
    } else {
      const handlers = this.listeners.get(event);
      if (handlers) {
        handlers.delete(targetHandler);
        if (handlers.size === 0) {
          this.listeners.delete(event);
        }
      }
    }

    // 清理 once 记录
    if (onceWrapper) {
      this.onceWrappers.delete(handler);
    }
  }

  /**
   * 获取当前注册的监听器数量（用于调试/测试）
   */
  get listenerCount(): number {
    let count = 0;
    this.listeners.forEach((handlers) => {
      count += handlers.size;
    });
    this.patternListeners.forEach((handlers) => {
      count += handlers.size;
    });
    return count;
  }

  /**
   * 清空所有监听器
   */
  clear(): void {
    this.listeners.clear();
    this.patternListeners.clear();
    this.onceWrappers = new WeakMap();
  }
}

// ============================
// 单例导出
// ============================

/** 全局服务事件总线实例 */
export const serviceEventBus = new ServiceEventBus();

export default serviceEventBus;
