/**
 * 伏羲 v2.1 — 八卦数据定义
 * 后天八卦九宫格布局（Phase 1 spec）
 *
 * 九宫布局：
 *   巽☴肺(4) | 离☲心(9) | 坤☷脾(2)
 *   震☳肝(3) | 中宫胃(5) | 兑☱鼻(7)
 *   艮☶皮肤(8)| 坎☵肾(1) | 乾☰大脑(6)
 *
 * 视觉规范色：
 *   乾金#F0C040 / 坤土#C8A96E / 震青#4CAF50
 *   巽绿#81C784 / 坎黑#424242 / 离红#E53935
 *   艮棕#8D6E63 / 兑白#FAFAFA
 */

/** 卦格状态枚举 */
export type TrigramStatus = 'healthy' | 'warning' | 'error' | 'offline';

/** 器官状态数据（从 /api/symbols/status） */
export interface OrganStatus {
  trigramId: string;
  status: TrigramStatus;
  activeTaskCount: number;
  label: string;
}

/** 八卦数据项 */
export interface TrigramData {
  id: string;
  label: string;
  symbol: string;
  route: string;
  routeName: string;
  color: string;
  colorLight: string;
  glowColor: string;
  emoji: string;
  wuxing: '金' | '木' | '水' | '火' | '土';
  /** 后天八卦宫位 1-9（5=中宫） */
  position: number;
  organ: string;
  functionDesc: string;
  yijingQuote: string;
  /** 快捷键数字 */
  shortcutKey: string;
}

export interface ZhonggongData {
  id: 'zhonggong';
  label: string;
  symbol: string;
  route: string;
  routeName: string;
  color: string;
  colorLight: string;
  glowColor: string;
  emoji: string;
  position: 5;
  organ: string;
  functionDesc: string;
  yijingQuote: string;
  shortcutKey: string;
}

export type BaguaItem = TrigramData | ZhonggongData;

/** 八卦定义（后天八卦，Phase 1 spec 颜色） */
export const BAGUA_LIST: readonly BaguaItem[] = [
  // ─── 第一行 ───
  {
    id: 'xun',
    label: '巽',
    symbol: '☴',
    route: '/workspace/wiki',
    routeName: 'Wiki',
    color: '#81C784',
    colorLight: '#E8F5E9',
    glowColor: 'rgba(129, 199, 132, 0.15)',
    emoji: '🌬️',
    wuxing: '木',
    position: 4,
    organ: '肺',
    functionDesc: '文档管理',
    yijingQuote: '随风巽，君子以申命行事。',
    shortcutKey: '4',
  },
  {
    id: 'li',
    label: '离',
    symbol: '☲',
    route: '/admin/evaluation',
    routeName: 'AdminEvaluation',
    color: '#E53935',
    colorLight: '#FFEBEE',
    glowColor: 'rgba(229, 57, 53, 0.15)',
    emoji: '🔥',
    wuxing: '火',
    position: 9,
    organ: '心',
    functionDesc: '评测中心',
    yijingQuote: '明两作离，大人以继明照于四方。',
    shortcutKey: '9',
  },
  {
    id: 'kun',
    label: '坤',
    symbol: '☷',
    route: '/knowledge',
    routeName: 'Knowledge',
    color: '#C8A96E',
    colorLight: '#FFF8E1',
    glowColor: 'rgba(200, 169, 110, 0.15)',
    emoji: '🌍',
    wuxing: '土',
    position: 2,
    organ: '脾',
    functionDesc: '知识库',
    yijingQuote: '地势坤，君子以厚德载物。',
    shortcutKey: '2',
  },

  // ─── 第二行 ───
  {
    id: 'zhen',
    label: '震',
    symbol: '☳',
    route: '/workspace/documents',
    routeName: 'Documents',
    color: '#4CAF50',
    colorLight: '#E8F5E9',
    glowColor: 'rgba(76, 175, 80, 0.15)',
    emoji: '⚡',
    wuxing: '木',
    position: 3,
    organ: '肝',
    functionDesc: '文档中心',
    yijingQuote: '洊雷震，君子以恐惧修省。',
    shortcutKey: '3',
  },
  {
    id: 'dui',
    label: '兑',
    symbol: '☱',
    route: '/workspace/chat',
    routeName: 'Chat',
    color: '#FAFAFA',
    colorLight: '#FAFAFA',
    glowColor: 'rgba(200, 200, 200, 0.2)',
    emoji: '💬',
    wuxing: '金',
    position: 7,
    organ: '鼻',
    functionDesc: 'AI 对话',
    yijingQuote: '丽泽兑，君子以朋友讲习。',
    shortcutKey: '7',
  },

  // ─── 第三行 ───
  {
    id: 'gen',
    label: '艮',
    symbol: '☶',
    route: '/admin',
    routeName: 'Admin',
    color: '#8D6E63',
    colorLight: '#EFEBE9',
    glowColor: 'rgba(141, 110, 99, 0.15)',
    emoji: '⛰️',
    wuxing: '土',
    position: 8,
    organ: '皮肤',
    functionDesc: '系统管理',
    yijingQuote: '兼山艮，君子以思不出其位。',
    shortcutKey: '8',
  },
  {
    id: 'kan',
    label: '坎',
    symbol: '☵',
    route: '/workspace/worldtree',
    routeName: 'WorldTree',
    color: '#424242',
    colorLight: '#EEEEEE',
    glowColor: 'rgba(66, 66, 66, 0.15)',
    emoji: '🌊',
    wuxing: '水',
    position: 1,
    organ: '肾',
    functionDesc: '数据精炼',
    yijingQuote: '水洊至坎，君子以常德行习教事。',
    shortcutKey: '1',
  },
  {
    id: 'qian',
    label: '乾',
    symbol: '☰',
    route: '/workspace/chat',
    routeName: 'Chat',
    color: '#F0C040',
    colorLight: '#FFFDE7',
    glowColor: 'rgba(240, 192, 64, 0.2)',
    emoji: '🧠',
    wuxing: '金',
    position: 6,
    organ: '大脑',
    functionDesc: 'AI 对话',
    yijingQuote: '天行健，君子以自强不息。',
    shortcutKey: '6',
  },
];

/** 中宫定义 */
export const ZHONGGONG: ZhonggongData = {
  id: 'zhonggong',
  label: '中宫',
  symbol: '⊙',
  route: '/',
  routeName: 'Home',
  color: '#FF6700',
  colorLight: '#FFF3E8',
  glowColor: 'rgba(255, 103, 0, 0.15)',
  emoji: '☯️',
  position: 5,
  organ: '胃',
  functionDesc: '首页中枢',
  yijingQuote: '太极生两仪，两仪生四象，四象生八卦。',
  shortcutKey: '5',
};

/** 按位置排序的完整九宫格（position 1-9） */
export const BAGUA_GRID: readonly (BaguaItem | null)[] = (() => {
  const grid: (BaguaItem | null)[] = new Array(10).fill(null);
  for (const item of BAGUA_LIST) {
    grid[item.position] = item;
  }
  grid[ZHONGGONG.position] = ZHONGGONG;
  return grid;
})();

/** 按卦 ID 索引八卦数据 */
export const BAGUA_BY_ID: Readonly<Record<string, BaguaItem>> = (() => {
  const map: Record<string, BaguaItem> = {};
  for (const item of BAGUA_LIST) {
    map[item.id] = item;
  }
  map[ZHONGGONG.id] = ZHONGGONG;
  return map;
})();

/** 卦格状态映射 */
export interface BaguaStatus {
  trigramId: string;
  status: TrigramStatus;
  value?: number;
  label?: string;
}
