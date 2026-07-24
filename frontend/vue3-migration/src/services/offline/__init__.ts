/**
 * 伏羲 v2.1 — 离线模式初始化插件
 *
 * 在应用启动时自动初始化 OfflineService，
 * 注册 Service Worker 消息处理。
 * 在 main.ts 中通过 app.use() 或手动调用 initOfflineMode() 来启用。
 */

import { createLogger } from '@/utils/logger';
import { offlineService } from './OfflineService';

const logger = createLogger('OfflineInit');

// ============================
// Service Worker 消息处理
// ============================

function setupSWMessageHandler(): void {
  if (!('serviceWorker' in navigator)) {
    logger.warn('当前浏览器不支持 Service Worker');
    return;
  }

  navigator.serviceWorker.addEventListener('message', (event) => {
    const { type, url, timestamp } = event.data || {};

    switch (type) {
      case 'API_FALLBACK':
        logger.debug('Service Worker 报告 API 降级', { url, timestamp });
        break;

      case 'PUSH_SUBSCRIPTION_CHANGE':
        logger.info('Push 订阅已更新', event.data.subscription);
        break;

      case 'API_CACHE_CLEARED':
        logger.info('API 缓存已清除');
        break;

      case 'ALL_CACHE_CLEARED':
        logger.info('所有缓存已清除');
        break;

      default:
        // 忽略未知消息
        break;
    }
  });

  logger.debug('Service Worker 消息处理已就绪');
}

// ============================
// 初始化函数
// ============================

let initialized = false;

/**
 * 初始化离线模式
 *
 * @param options.initServiceWorker - 是否初始化 Service Worker 消息处理
 */
export async function initOfflineMode(options?: {
  initServiceWorker?: boolean;
}): Promise<void> {
  if (initialized) {
    logger.warn('离线模式已初始化，跳过');
    return;
  }

  logger.info('初始化离线模式...');

  try {
    // 初始化离线服务核心
    await offlineService.init();

    // 初始化 Service Worker 消息处理
    if (options?.initServiceWorker !== false) {
      setupSWMessageHandler();
    }

    initialized = true;
    logger.info('离线模式初始化完成');
  } catch (err) {
    logger.error('离线模式初始化失败', err);
    throw err;
  }
}

/**
 * 检查离线模式是否已初始化
 */
export function isOfflineModeInitialized(): boolean {
  return initialized;
}

/**
 * 销毁离线模式
 */
export function disposeOfflineMode(): void {
  offlineService.destroy();
  initialized = false;
  logger.info('离线模式已销毁');
}
