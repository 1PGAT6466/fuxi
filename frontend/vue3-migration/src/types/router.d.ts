/**
 * Vue Router 模块声明扩展
 * 定义路由元信息类型，确保路由配置的类型安全
 */

declare module 'vue-router' {
  interface RouteMeta {
    /** 是否需要认证 */
    requiresAuth?: boolean;
    /** 是否需要管理员权限 */
    requiresAdmin?: boolean;
    /** 页面标题 */
    title?: string;
  }
}

export {};
