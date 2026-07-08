/**
 * 伏羲 v2.1 — 统一 Logger
 *
 * 所有日志输出通过此模块统一管理：
 * - 自动添加 [伏羲] 前缀和模块名
 * - 支持 info / warn / error / debug 四个级别
 * - 可通过 VITE_LOG_LEVEL 环境变量控制输出级别
 *   （'debug' | 'info' | 'warn' | 'error' | 'silent'，默认 'debug'）
 *
 * 用法：
 *   import { createLogger } from '@/utils/logger';
 *   const logger = createLogger('Router');
 *   logger.info('路由初始化完成');
 */

// ============================
// 日志级别
// ============================

const LOG_LEVELS: Record<string, number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
  silent: 4,
};

const currentLevel: number =
  LOG_LEVELS[import.meta.env.VITE_LOG_LEVEL as string] ?? LOG_LEVELS.debug;

const LOG_PREFIX = '[伏羲]';

// ============================
// Logger 接口
// ============================

export interface Logger {
  info: (...args: unknown[]) => void;
  warn: (...args: unknown[]) => void;
  error: (...args: unknown[]) => void;
  debug: (...args: unknown[]) => void;
}

// ============================
// Logger 工厂
// ============================

/**
 * 创建一个带模块名的 logger 实例。
 *
 * @param moduleName - 模块标识，如 'Router'、'AuthStore'、'ServiceLoader'
 * @returns Logger 实例
 *
 * @example
 *   const logger = createLogger('ChatStore');
 *   logger.info('消息发送成功', { sessionId: 'abc' });
 *   logger.error('SSE 连接失败', err);
 */
export function createLogger(moduleName: string): Logger {
  const prefix = `${LOG_PREFIX}[${moduleName}]`;

  return {
    debug(...args: unknown[]): void {
      if (currentLevel <= LOG_LEVELS.debug) {
        console.debug(prefix, ...args);
      }
    },

    info(...args: unknown[]): void {
      if (currentLevel <= LOG_LEVELS.info) {
        console.info(prefix, ...args);
      }
    },

    warn(...args: unknown[]): void {
      if (currentLevel <= LOG_LEVELS.warn) {
        console.warn(prefix, ...args);
      }
    },

    error(...args: unknown[]): void {
      if (currentLevel <= LOG_LEVELS.error) {
        console.error(prefix, ...args);
      }
    },
  };
}

// ============================
// 顶级便捷导出（无模块名，用于快速替换）
// ============================

export const logger: Logger = createLogger('App');
