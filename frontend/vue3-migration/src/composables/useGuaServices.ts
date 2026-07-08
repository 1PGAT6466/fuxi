/**
 * useGuaServices — 卦位-服务映射 Composable
 *
 * 从 ServiceRegistry 获取所有服务，按 guaAffinity 分组
 * 返回 Record<GuaSymbol, ServiceManifest[]>
 * 用于 BaguaCell 的下拉菜单
 */

import { computed } from 'vue';

// ============================================
// 类型定义
// ============================================

/** 八卦符号枚举 */
export type GuaSymbol = 'qian' | 'kun' | 'zhen' | 'xun' | 'kan' | 'li' | 'gen' | 'dui';

/** 服务清单 */
export interface ServiceManifest {
  id: string;
  name: string;
  description: string;
  icon?: string;
  /** 归属卦位 */
  guaAffinity: GuaSymbol;
  /** 服务路由或窗口 ID */
  route: string;
  /** 是否为活动服务 */
  isActive?: boolean;
  /** 活跃任务数 */
  activeTaskCount?: number;
  /** 服务状态 */
  status?: 'online' | 'degraded' | 'offline';
}

/** 按卦位分组的服务映射 */
export type GuaServiceMap = Record<GuaSymbol, ServiceManifest[]>;

// ============================================
// 内置服务注册表
// 后续可通过 /api/services/manifest 动态获取
// ============================================

const BUILTIN_SERVICES: ServiceManifest[] = [
  // ─── 乾 ☰ — 大脑 / AI 对话 ───
  {
    id: 'chat-assistant',
    name: '智能对话',
    description: 'AI 多模态对话助手',
    icon: '🧠',
    guaAffinity: 'qian',
    route: '/workspace/chat',
    isActive: true,
    activeTaskCount: 1,
    status: 'online',
  },
  {
    id: 'sql-assistant',
    name: 'SQL 助手',
    description: '自然语言查询数据库',
    icon: '🗄️',
    guaAffinity: 'qian',
    route: '/workspace/chat?mode=sql',
    isActive: false,
    activeTaskCount: 0,
    status: 'online',
  },
  // ─── 坤 ☷ — 脾 / 知识库 ───
  {
    id: 'knowledge-base',
    name: '知识库管理',
    description: '企业知识文档管理',
    icon: '📚',
    guaAffinity: 'kun',
    route: '/workspace/documents',
    isActive: true,
    activeTaskCount: 3,
    status: 'online',
  },
  {
    id: 'wiki-editor',
    name: 'Wiki 编辑',
    description: '协作 Wiki 文档',
    icon: '📝',
    guaAffinity: 'kun',
    route: '/workspace/wiki',
    isActive: false,
    activeTaskCount: 0,
    status: 'online',
  },
  {
    id: 'graph-knowledge',
    name: '知识图谱',
    description: '知识关系可视化',
    icon: '🔗',
    guaAffinity: 'kun',
    route: '/workspace/graph',
    isActive: false,
    activeTaskCount: 0,
    status: 'online',
  },
  // ─── 震 ☳ — 肝 / 文档消化 ───
  {
    id: 'doc-parser',
    name: '文档解析',
    description: '多格式文档智能解析',
    icon: '📄',
    guaAffinity: 'zhen',
    route: '/workspace/documents?action=upload',
    isActive: true,
    activeTaskCount: 2,
    status: 'online',
  },
  {
    id: 'file-manager',
    name: '文件管理',
    description: '文件上传与管理',
    icon: '📁',
    guaAffinity: 'zhen',
    route: '/files',
    isActive: false,
    activeTaskCount: 0,
    status: 'online',
  },
  // ─── 巽 ☴ — 肺 / 知识检索 ───
  {
    id: 'semantic-search',
    name: '语义搜索',
    description: '向量语义检索',
    icon: '🔍',
    guaAffinity: 'xun',
    route: '/search',
    isActive: true,
    activeTaskCount: 1,
    status: 'online',
  },
  {
    id: 'fulltext-index',
    name: '全文索引',
    description: '全文搜索引擎',
    icon: '📇',
    guaAffinity: 'xun',
    route: '/search?mode=fulltext',
    isActive: false,
    activeTaskCount: 0,
    status: 'online',
  },
  // ─── 坎 ☵ — 肾 / 数据精炼 ───
  {
    id: 'data-pipeline',
    name: '数据管道',
    description: 'ETL 数据精炼流程',
    icon: '⚙️',
    guaAffinity: 'kan',
    route: '/workspace/worldtree',
    isActive: true,
    activeTaskCount: 5,
    status: 'degraded',
  },
  // ─── 离 ☲ — 心 / 决策判断 ───
  {
    id: 'decision-engine',
    name: '决策引擎',
    description: '智能推理与决策',
    icon: '⚖️',
    guaAffinity: 'li',
    route: '/workspace/graph?mode=decision',
    isActive: false,
    activeTaskCount: 0,
    status: 'online',
  },
  // ─── 艮 ☶ — 皮肤 / 系统守卫 ───
  {
    id: 'system-monitor',
    name: '系统监控',
    description: '健康检查与告警',
    icon: '🛡️',
    guaAffinity: 'gen',
    route: '/admin',
    isActive: true,
    activeTaskCount: 0,
    status: 'online',
  },
  {
    id: 'auth-guard',
    name: '认证守卫',
    description: '用户认证与权限管理',
    icon: '🔐',
    guaAffinity: 'gen',
    route: '/admin?tab=users',
    isActive: false,
    activeTaskCount: 0,
    status: 'online',
  },
  // ─── 兑 ☱ — 鼻 / 响应呈现 ───
  {
    id: 'report-builder',
    name: '报告生成',
    description: '可视化报告构建器',
    icon: '📊',
    guaAffinity: 'dui',
    route: '/workspace/documents?action=report',
    isActive: false,
    activeTaskCount: 0,
    status: 'online',
  },
  {
    id: 'api-gateway',
    name: 'API 网关',
    description: '对外 API 管理',
    icon: '🌐',
    guaAffinity: 'dui',
    route: '/admin?tab=api',
    isActive: true,
    activeTaskCount: 12,
    status: 'online',
  },
];

// ============================================
// Composable
// ============================================

/** 服务注册表（模块级单例，可被外部更新） */
let serviceRegistry: ServiceManifest[] = [...BUILTIN_SERVICES];

export function useGuaServices() {
  /** 按卦位分组的服务映射 */
  const guaServiceMap = computed<GuaServiceMap>(() => {
    const map: GuaServiceMap = {
      qian: [],
      kun: [],
      zhen: [],
      xun: [],
      kan: [],
      li: [],
      gen: [],
      dui: [],
    };

    for (const service of serviceRegistry) {
      map[service.guaAffinity].push(service);
    }

    return map;
  });

  /** 获取特定卦位的服务列表 */
  function getServicesForGua(gua: GuaSymbol): ServiceManifest[] {
    return serviceRegistry.filter((s) => s.guaAffinity === gua);
  }

  /** 获取特定卦位的活跃任务总数 */
  function getActiveTaskCountForGua(gua: GuaSymbol): number {
    return serviceRegistry
      .filter((s) => s.guaAffinity === gua)
      .reduce((sum, s) => sum + (s.activeTaskCount || 0), 0);
  }

  /** 获取特定卦位的在线服务数 */
  function getOnlineServiceCountForGua(gua: GuaSymbol): number {
    return serviceRegistry.filter((s) => s.guaAffinity === gua).filter((s) => s.status === 'online')
      .length;
  }

  /** 更新服务注册表 */
  function updateServiceRegistry(services: ServiceManifest[]): void {
    serviceRegistry = services;
  }

  /** 从 API 获取服务清单并更新注册表 */
  async function fetchServiceManifest(): Promise<void> {
    try {
      const response = await fetch('/api/services/manifest');
      if (response.ok) {
        const data = await response.json();
        if (data.data && Array.isArray(data.data)) {
          serviceRegistry = data.data;
        }
      }
    } catch {
      // 静默回退到内置注册表
    }
  }

  /** 所有服务总数 */
  const totalServices = computed(() => serviceRegistry.length);

  /** 平台总活跃任务数 */
  const totalActiveTasks = computed(() =>
    serviceRegistry.reduce((sum, s) => sum + (s.activeTaskCount || 0), 0),
  );

  /** 平台总在线服务数 */
  const totalOnlineServices = computed(
    () => serviceRegistry.filter((s) => s.status === 'online').length,
  );

  return {
    /** 纯数据：所有服务 */
    services: serviceRegistry,
    /** 按卦分组的服务映射 */
    guaServiceMap,
    /** 获取某卦的服务列表 */
    getServicesForGua,
    /** 获取某卦的活跃任务数 */
    getActiveTaskCountForGua,
    /** 获取某卦的在线服务数 */
    getOnlineServiceCountForGua,
    /** 更新服务注册表 */
    updateServiceRegistry,
    /** 从 API 获取服务清单 */
    fetchServiceManifest,
    /** 统计 */
    totalServices,
    totalActiveTasks,
    totalOnlineServices,
  };
}
