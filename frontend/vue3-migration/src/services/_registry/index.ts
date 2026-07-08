/**
 * 伏羲 v2.1 — 服务注册中心统一导出
 */

export { serviceLoader } from './ServiceLoader';
export { serviceRegistry } from './ServiceRegistry';
export {
  createServiceRoute,
  registerServiceRoutes,
  createServiceRouteComponent,
} from './ServiceRouter';
export { default as ServiceWindowShell } from './ServiceWindowShell.vue';
export { serviceEventBus } from './ServiceEventBus';
