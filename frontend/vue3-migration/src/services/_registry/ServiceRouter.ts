/**
 * 伏羲 v2.1 — 服务路由
 *
 * 功能：
 * - 将 ServiceManifest 动态注册为 Vue Router 子路由
 * - 支持路由名称、路径、元信息的自动生成
 * - 与窗口管理器联动，在路由变化时自动聚焦对应窗口
 */

import { defineComponent } from 'vue';
import type { RouteRecordRaw, Router } from 'vue-router';
import type { ServiceManifest } from '@/types/service-manifest';

/**
 * 根据 ServiceManifest 生成 Vue Router 路由配置
 *
 * 每个服务路由都包含元信息（serviceId, guaAffinity, windowMode 等），
 * 以便窗口管理器根据路由激活来定位正确的 ServiceWindow。
 */
export function createServiceRoute(
  manifest: ServiceManifest,
  component: () => Promise<unknown>,
): RouteRecordRaw {
  return {
    path: manifest.route.startsWith('/') ? manifest.route : `/${manifest.route}`,
    name: `service-${manifest.id}`,
    component: () => component(),
    meta: {
      serviceId: manifest.id,
      serviceName: manifest.name,
      icon: manifest.icon,
      category: manifest.category,
      guaAffinity: manifest.guaAffinity,
      windowMode: manifest.windowMode,
      defaultSize: manifest.defaultSize,
      singleton: manifest.singleton ?? false,
      requiresAuth: true,
      title: manifest.name,
    },
  };
}

/**
 * 创建通用服务路由组件（懒加载占位符）
 *
 * 实际的服务组件由 ServiceWindowShell 通过 KeepAlive 管理。
 * 这里返回一个简单的占位组件，由窗口管理器接管渲染。
 */
export function createServiceRouteComponent(manifest: ServiceManifest) {
  return defineComponent({
    name: `ServicePage-${manifest.id}`,
    setup() {
      // 这个组件只是一个路由占位符
      // 实际的窗口UI由 ServiceWindowShell 通过 keep-alive 管理
      return () => null;
    },
  });
}

/**
 * 将一组 ServiceManifest 注册为指定路由的子路由
 *
 * @param router - Vue Router 实例
 * @param parentPath - 父路由路径（如 '/'）
 * @param manifests - 要注册的服务清单列表
 */
export function registerServiceRoutes(
  router: Router,
  parentPath: string,
  manifests: ServiceManifest[],
): void {
  const newRoutes = manifests.map((m) =>
    createServiceRoute(m, () => import('@/components/common/ServicePlaceholder.vue')),
  );

  for (const route of newRoutes) {
    // 检查是否已存在同名路由
    if (router.hasRoute(route.name as string)) {
      console.warn(`[ServiceRouter] 路由 "${route.name}" 已存在，跳过注册`);
      continue;
    }
    router.addRoute(parentPath, route);
  }

  console.log(`[ServiceRouter] 注册了 ${manifests.length} 个服务路由`);
}
