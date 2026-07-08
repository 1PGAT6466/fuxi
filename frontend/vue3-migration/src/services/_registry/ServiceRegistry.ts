/**
 * 伏羲 v2.1 — 服务注册表
 *
 * 功能：
 * - 全局服务注册表单例
 * - getAll / getById / getByCategory / getEnabled
 * - register 手动注册（用于测试或动态加载）
 * - 与 ServiceLoader 集成，自动加载 manifest
 */

import { createLogger } from '@/utils/logger';
const logger = createLogger('ServiceRegistry');

import type { ServiceManifest, ServiceCategory } from '@/types/service-manifest';
import { serviceLoader } from './ServiceLoader';

class ServiceRegistry {
  /** 服务注册表映射：id → ServiceManifest */
  private services: Map<string, ServiceManifest> = new Map();

  /** 是否已初始化 */
  private initialized: boolean = false;

  /** 初始化 promise（防止重复初始化） */
  private initPromise: Promise<void> | null = null;

  /**
   * 初始化注册表（从 ServiceLoader 加载所有服务）
   */
  async init(): Promise<void> {
    if (this.initialized) return;
    if (this.initPromise) {
      await this.initPromise;
      return;
    }

    this.initPromise = serviceLoader.loadAll().then((manifests) => {
      for (const manifest of manifests) {
        this.services.set(manifest.id, manifest);
      }
      this.initialized = true;
      logger.info(`[ServiceRegistry] 注册完成: ${this.services.size} 个服务`);
    });

    await this.initPromise;
  }

  /**
   * 手动注册服务（用于测试或动态扩展）
   */
  register(manifest: ServiceManifest): void {
    if (this.services.has(manifest.id)) {
      console.warn(`[ServiceRegistry] 服务 "${manifest.id}" 已存在，将被覆盖`);
    }
    this.services.set(manifest.id, manifest);
  }

  /**
   * 获取所有已注册服务
   */
  getAll(): ServiceManifest[] {
    return Array.from(this.services.values());
  }

  /**
   * 按 ID 获取服务
   */
  getById(id: string): ServiceManifest | undefined {
    return this.services.get(id);
  }

  /**
   * 按分类获取服务列表
   */
  getByCategory(category: ServiceCategory): ServiceManifest[] {
    return this.getAll().filter((s) => s.category === category);
  }

  /**
   * 获取当前用户可用的服务（已启用 + 权限满足）
   *
   * @param userRole - 当前用户角色
   */
  getEnabled(userRole: 'user' | 'admin' = 'user'): ServiceManifest[] {
    return this.getAll().filter((s) => {
      if (s.requiredRole === 'admin' && userRole !== 'admin') return false;
      return true;
    });
  }

  /**
   * 检查服务是否存在
   */
  has(id: string): boolean {
    return this.services.has(id);
  }

  /**
   * 获取服务数量
   */
  get count(): number {
    return this.services.size;
  }

  /**
   * 重置注册表（主要用于测试）
   */
  reset(): void {
    this.services.clear();
    this.initialized = false;
    this.initPromise = null;
  }
}

// ============================
// 单例导出
// ============================

export const serviceRegistry = new ServiceRegistry();
export default serviceRegistry;
