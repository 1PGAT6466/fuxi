/**
 * 伏羲 v2.1 — 服务加载器
 *
 * 功能：
 * - 从静态导入清单加载所有服务 manifest.json
 * - 校验 manifest 结构完整性
 * - 按 feature flag 过滤不可用服务
 *
 * 注意：STATIC_MANIFESTS 是本模块的唯一定义来源；
 * 添加新服务时仅需在此数组中新增一项，router 的 initServiceRoutes
 * 通过 ServiceRegistry.getAll() 自动获取，无需单独维护。
 */

import { createLogger } from '@/utils/logger';
import type {
  ServiceManifest,
  EndpointDef,
  GuaSymbol,
  WindowMode,
  ServiceCategory,
} from '@/types/service-manifest';

const logger = createLogger('ServiceLoader');

// ============================
// Manifest JSON 校验
// ============================

const VALID_CATEGORIES: ServiceCategory[] = [
  'workspace',
  'analytics',
  'engineering',
  'admin',
  'personal',
];
const VALID_WINDOW_MODES: WindowMode[] = ['tab', 'modal', 'drawer', 'fullscreen'];
const VALID_GUA_SYMBOLS: GuaSymbol[] = ['qian', 'kun', 'zhen', 'xun', 'kan', 'li', 'gen', 'dui'];
const VALID_METHODS = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'];
const VALID_ROLES = ['user', 'admin'];

function isValidGuaSymbol(value: unknown): value is GuaSymbol {
  return typeof value === 'string' && VALID_GUA_SYMBOLS.includes(value as GuaSymbol);
}

function isValidEndpoint(value: unknown): value is EndpointDef {
  if (!value || typeof value !== 'object') return false;
  const ep = value as Record<string, unknown>;
  return (
    typeof ep.path === 'string' &&
    typeof ep.description === 'string' &&
    typeof ep.method === 'string' &&
    VALID_METHODS.includes(ep.method)
  );
}

function isValidManifest(obj: unknown): obj is ServiceManifest {
  if (!obj || typeof obj !== 'object') return false;
  const m = obj as Record<string, unknown>;

  if (
    typeof m.id !== 'string' ||
    typeof m.name !== 'string' ||
    typeof m.icon !== 'string' ||
    typeof m.description !== 'string' ||
    typeof m.version !== 'string' ||
    typeof m.route !== 'string' ||
    typeof m.apiBase !== 'string'
  ) {
    logger.warn('manifest 缺少必填字符串字段:', m.id);
    return false;
  }

  if (!VALID_CATEGORIES.includes(m.category as ServiceCategory)) {
    logger.warn(`manifest "${m.id}" 的 category "${m.category}" 无效`);
    return false;
  }

  if (!VALID_WINDOW_MODES.includes(m.windowMode as WindowMode)) {
    logger.warn(`manifest "${m.id}" 的 windowMode "${m.windowMode}" 无效`);
    return false;
  }

  if (!VALID_ROLES.includes(m.requiredRole as string)) {
    logger.warn(`manifest "${m.id}" 的 requiredRole "${m.requiredRole}" 无效`);
    return false;
  }

  if (!Array.isArray(m.endpoints)) {
    logger.warn(`manifest "${m.id}" 的 endpoints 不是数组`);
    return false;
  }

  for (let i = 0; i < m.endpoints.length; i++) {
    if (!isValidEndpoint(m.endpoints[i])) {
      logger.warn(`manifest "${m.id}" 的 endpoints[${i}] 无效`);
      return false;
    }
  }

  if (m.guaAffinity !== undefined) {
    const ga = m.guaAffinity as Record<string, unknown>;
    if (
      typeof ga !== 'object' ||
      !isValidGuaSymbol(ga.primary) ||
      !isValidGuaSymbol(ga.secondary)
    ) {
      logger.warn(`manifest "${m.id}" 的 guaAffinity 无效`);
      return false;
    }
  }

  return true;
}

// ============================
// 静态导入清单（唯一来源）
// ============================

/**
 * 所有服务 manifest 的 Vite 静态导入映射。
 *
 * 新增服务时，在此对象中新增一项即可完成注册。
 * 无需修改 router、ServiceRegistry 或其他模块。
 */
const STATIC_MANIFESTS: Record<string, () => Promise<{ default: unknown }>> = {
  'ai-tools': () => import('@/services/ai-tools/manifest.json'),
  'data-analytics': () => import('@/services/data-analytics/manifest.json'),
  'doc-tools': () => import('@/services/doc-tools/manifest.json'),
  'dxf-viewer': () => import('@/services/dxf-viewer/manifest.json'),
  'recent-visits': () => import('@/services/recent-visits/manifest.json'),
  'notification-center': () => import('@/services/notification-center/manifest.json'),
  'favorites': () => import('@/services/favorites/manifest.json'),
  'collaboration': () => import('@/services/collaboration/manifest.json'),
  'api-keys': () => import('@/services/api-keys/manifest.json'),
  'service-market': () => import('@/services/service-market/manifest.json'),
  'webhooks': () => import('@/services/webhooks/manifest.json'),
  'developer-portal': () => import('@/services/developer-portal/manifest.json'),
};

// ============================
// 服务加载器
// ============================

class ServiceLoader {
  private loadedManifests: ServiceManifest[] | null = null;
  private loadingPromise: Promise<ServiceManifest[]> | null = null;
  private enabledFlags: Set<string> = new Set();

  setEnabledFlags(flags: string[]): void {
    this.enabledFlags = new Set(flags);
  }

  async loadAll(): Promise<ServiceManifest[]> {
    if (this.loadedManifests) {
      return Promise.resolve(this.filterByFlag(this.loadedManifests));
    }

    if (this.loadingPromise) {
      return this.loadingPromise;
    }

    this.loadingPromise = this.loadFromStatic().then((manifests) => {
      this.loadedManifests = manifests;
      return this.filterByFlag(manifests);
    });

    return this.loadingPromise;
  }

  private async loadFromStatic(): Promise<ServiceManifest[]> {
    const manifests: ServiceManifest[] = [];
    const entries = Object.entries(STATIC_MANIFESTS);

    for (const [key, loader] of entries) {
      try {
        const mod = await loader();
        const data = (mod as { default?: unknown }).default || mod;
        if (isValidManifest(data)) {
          manifests.push(data);
        }
      } catch (err) {
        logger.error(`加载 manifest 失败: "${key}"`, err);
      }
    }

    logger.info(`成功加载 ${manifests.length} 个服务清单`);
    return manifests;
  }

  private filterByFlag(manifests: ServiceManifest[]): ServiceManifest[] {
    if (this.enabledFlags.size === 0) {
      return manifests;
    }

    return manifests.filter((m) => {
      if (!m.featureFlag) return true;
      return this.enabledFlags.has(m.featureFlag);
    });
  }
}

// ============================
// 单例导出
// ============================

export const serviceLoader = new ServiceLoader();
export default serviceLoader;
