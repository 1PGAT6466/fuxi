import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { serviceRegistry } from '@/services/_registry/ServiceRegistry';
import { registerServiceRoutes } from '@/services/_registry/ServiceRouter';
import TokenManager from '@/utils/TokenManager';
import { createLogger } from '@/utils/logger';
import type { ServiceManifest } from '@/types/service-manifest';

const logger = createLogger('Router');

// 用于标记是否已完成动态注册
let serviceRoutesRegistered = false;

/** 初始化动态服务路由 */
export async function initServiceRoutes(): Promise<void> {
  if (serviceRoutesRegistered) return;
  await serviceRegistry.init();
  const manifests = serviceRegistry.getAll();

  // 过滤掉路由表中已静态注册的服务（通过已有 route name 判定，无需维护硬编码列表）
  const dynamicManifests = manifests.filter(
    (m: ServiceManifest) => !router.hasRoute(`service-${m.id}`),
  );

  if (dynamicManifests.length > 0) {
    registerServiceRoutes(router, '/', dynamicManifests);
  }

  serviceRoutesRegistered = true;
  logger.info(`动态注册完成: ${dynamicManifests.length} 个新服务路由`);
}

// ============================================
// 路由懒加载
// ============================================

// 无需认证
const LoginView = () => import('@/views/Login.vue');

// 主布局
const MainLayout = () => import('@/layouts/MainLayout.vue');

// 首页
const HomeView = () => import('@/views/HomeView.vue');

// 工作区
const ChatView = () => import('@/views/ChatView.vue');
const DocumentsView = () => import('@/views/DocumentsView.vue');
const WikiView = () => import('@/views/Wiki.vue');
const GraphView = () => import('@/views/GraphView.vue');
const WorldTreeView = () => import('@/views/WorldTreeView.vue');

// 知识库（独立路由，保留兼容）
const KnowledgeView = () => import('@/views/KnowledgeView.vue');
const SearchView = () => import('@/views/Search.vue');
const FilesView = () => import('@/views/Files.vue');

// Phase 2 新增
const FilesCenterView = () => import('@/views/FilesView.vue');
const RagTestView = () => import('@/views/RagTestView.vue');
const AiToolsPage = () => import('@/services/ai-tools/AiToolsPage.vue');
const DataAnalyticsPage = () => import('@/services/data-analytics/DataAnalyticsPage.vue');
const DocToolsPage = () => import('@/services/doc-tools/DocToolsPage.vue');

// Phase 3 — DXF 查看器
const DxfViewerPage = () => import('@/services/dxf-viewer/DxfViewerPage.vue');

// Phase 4 — 管理中心
const DashboardView = () => import('@/views/admin/DashboardView.vue');
const EvaluationView = () => import('@/views/admin/EvaluationView.vue');
const EvolutionView = () => import('@/views/admin/EvolutionView.vue');
const FeatureFlagsView = () => import('@/views/admin/FeatureFlagsView.vue');
const UserManagement = () => import('@/views/admin/UserManagement.vue');

// Phase 2 — 管理中心补充
const SymbolsView = () => import('@/views/admin/SymbolsView.vue');
const GrowthView = () => import('@/views/admin/GrowthView.vue');
const FeedbackView = () => import('@/views/admin/FeedbackView.vue');

// 管理
const AdminView = () => import('@/views/Admin.vue');

// 404
const NotFound = () => import('@/views/NotFound.vue');

// ============================================
// 路由配置
// ============================================

const routes: RouteRecordRaw[] = [
  // ─── 登录（无需认证） ───
  {
    path: '/login',
    name: 'Login',
    component: LoginView,
    meta: { requiresAuth: false, title: '登录' },
  },

  // ─── 主布局 — 所有需认证路由 ───
  {
    path: '/',
    component: MainLayout,
    meta: { requiresAuth: true },
    children: [
      // 首页 — 九宫格
      {
        path: '',
        name: 'Home',
        component: HomeView,
        meta: { title: '伏羲' },
      },

      // ─── 工作区 ───
      {
        path: 'workspace/chat',
        name: 'Chat',
        component: ChatView,
        meta: { title: 'AI 对话' },
      },
      {
        path: 'workspace/documents',
        name: 'Documents',
        component: DocumentsView,
        meta: { title: '文档中心' },
      },
      {
        path: 'workspace/files',
        name: 'FilesCenter',
        component: FilesCenterView,
        meta: { title: '文件中心' },
      },
      {
        path: 'workspace/wiki',
        name: 'Wiki',
        component: WikiView,
        meta: { title: 'Wiki' },
      },
      {
        path: 'workspace/wiki/:id',
        name: 'WikiDetail',
        component: WikiView,
        props: true,
        meta: { title: 'Wiki 详情' },
      },
      {
        path: 'workspace/graph',
        name: 'Graph',
        component: GraphView,
        meta: { title: '知识图谱' },
      },
      {
        path: 'workspace/worldtree',
        name: 'WorldTree',
        component: WorldTreeView,
        meta: { title: '世界树' },
      },
      {
        path: 'workspace/rag-test',
        name: 'RagTest',
        component: RagTestView,
        meta: { title: 'RAG测试台' },
      },
      {
        path: 'workspace/ai-tools',
        name: 'AiTools',
        component: AiToolsPage,
        meta: { title: 'AI 工具集' },
      },
      {
        path: 'workspace/analytics',
        name: 'analytics',
        component: DataAnalyticsPage,
        meta: { title: '数据分析' },
      },
      {
        path: 'workspace/doc-tools',
        name: 'doc-tools',
        component: DocToolsPage,
        meta: { title: '文档工具' },
      },

      // ─── 兼容路由（旧版） ───
      {
        path: 'chat',
        redirect: '/workspace/chat',
      },
      {
        path: 'knowledge',
        name: 'Knowledge',
        component: KnowledgeView,
        meta: { title: '知识库' },
      },
      {
        path: 'search',
        name: 'Search',
        component: SearchView,
        meta: { title: '知识检索' },
      },
      {
        path: 'files',
        name: 'Files',
        component: FilesView,
        meta: { title: '文件管理' },
      },
      {
        path: 'wiki',
        redirect: '/workspace/wiki',
      },
      {
        path: 'wiki/:id',
        redirect: (to) => `/workspace/wiki/${to.params.id as string}`,
      },

      // ─── 占位路由 — 功能规划中，建设中 ───
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/views/Placeholder.vue'),
        meta: { title: '个人中心（建设中）' },
      },
      {
        path: 'about',
        name: 'About',
        component: () => import('@/views/Placeholder.vue'),
        meta: { title: '关于伏羲（建设中）' },
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/views/Placeholder.vue'),
        meta: { title: '设置（建设中）' },
      },

      // ─── DXF 查看器 ───
      {
        path: 'dxf-viewer',
        name: 'DxfViewer',
        component: DxfViewerPage,
        meta: { title: 'DXF 工程浏览器' },
      },

      // ─── 管理中心 ───
      {
        path: 'admin',
        name: 'Admin',
        component: AdminView,
        meta: { requiresAdmin: true, title: '管理中心' },
      },
      {
        path: 'admin/dashboard',
        name: 'AdminDashboard',
        component: DashboardView,
        meta: { requiresAdmin: true, title: '系统仪表板' },
      },
      {
        path: 'admin/evaluation',
        name: 'AdminEvaluation',
        component: EvaluationView,
        meta: { requiresAdmin: true, title: '评测管理' },
      },
      {
        path: 'admin/evolution',
        name: 'AdminEvolution',
        component: EvolutionView,
        meta: { requiresAdmin: true, title: '自进化管理' },
      },
      {
        path: 'admin/feature-flags',
        name: 'AdminFeatureFlags',
        component: FeatureFlagsView,
        meta: { requiresAdmin: true, title: '功能开关' },
      },
      {
        path: 'admin/users',
        name: 'AdminUsers',
        component: UserManagement,
        meta: { requiresAdmin: true, title: '用户管理' },
      },
      {
        path: 'admin/symbols',
        name: 'AdminSymbols',
        component: SymbolsView,
        meta: { requiresAdmin: true, title: '四象系统' },
      },
      {
        path: 'admin/growth',
        name: 'AdminGrowth',
        component: GrowthView,
        meta: { requiresAdmin: true, title: '成长面板' },
      },
      {
        path: 'admin/feedback',
        name: 'AdminFeedback',
        component: FeedbackView,
        meta: { requiresAdmin: true, title: '用户反馈' },
      },
      {
        path: 'admin/:section',
        name: 'AdminSection',
        component: AdminView,
        props: true,
        meta: { requiresAdmin: true, title: '管理中心' },
      },
    ],
  },

  // ─── 404 ───
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: NotFound,
  },
];

// ============================================
// 路由实例
// ============================================

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 };
  },
});

// ============================================
// JWT Token 工具 — 全部委托给 TokenManager
// ============================================

// ============================================
// 路由守卫
// ============================================

let fetchUserPromise: Promise<unknown> | null = null;
let lastFetchTime: number = 0;
const FETCH_CACHE_MS: number = 30_000; // 30 秒内不重复请求

router.beforeEach(async (to, _from, next) => {
  const authStore = useAuthStore();

  // 设置页面标题
  if (to.meta.title) {
    document.title = `${to.meta.title} | 伏羲`;
  }

  // ─── 无需认证的路由 ───
  if (to.meta.requiresAuth === false) {
    // 已登录时访问登录页 → 重定向到首页
    if (to.path === '/login' && authStore.isAuthenticated) {
      next('/');
      return;
    }
    next();
    return;
  }

  // ─── 需要认证的路由 ───
  const currentToken = authStore.token;

  // 没有 token → 跳转登录
  if (!currentToken) {
    next(`/login?redirect=${encodeURIComponent(to.fullPath)}`);
    return;
  }

  // ─── B10.1: Token 过期检测 ───
  if (TokenManager.isExpired(currentToken)) {
    logger.warn('Token 已过期，清除并跳转登录页');
    TokenManager.clearToken();
    await authStore.logout().catch(() => {});
    next(`/login?redirect=${encodeURIComponent(to.fullPath)}`);
    return;
  }

  // ─── B10.2: Token 即将过期 — 尝试自动刷新 ───
  if (TokenManager.isExpiringSoon(currentToken)) {
    logger.info('Token 即将过期，尝试自动刷新...');
    const newToken = await TokenManager.refreshToken();

    if (newToken) {
      logger.info('Token 刷新成功');
      authStore.token = newToken;
    } else {
      // ─── B10.3: 刷新失败 ───
      logger.warn('Token 刷新失败，清除认证数据并跳转登录页');
      TokenManager.clearToken();
      await authStore.logout().catch(() => {});
      next(`/login?redirect=${encodeURIComponent(to.fullPath)}`);
      return;
    }
  }

  // 有 token 但无用户信息 → 尝试获取
  if (!authStore.user && (!lastFetchTime || Date.now() - lastFetchTime > FETCH_CACHE_MS)) {
    try {
      if (!fetchUserPromise) {
        lastFetchTime = Date.now();
        fetchUserPromise = authStore.fetchUser().finally(() => {
          fetchUserPromise = null;
        });
      }
      await fetchUserPromise;
    } catch {
      await authStore.logout();
      next(`/login?redirect=${encodeURIComponent(to.fullPath)}`);
      return;
    }
  }

  // 管理员权限检查
  if (to.meta.requiresAdmin && !authStore.isAdmin) {
    next({ path: '/', replace: true });
    return;
  }

  next();
});

export default router;
