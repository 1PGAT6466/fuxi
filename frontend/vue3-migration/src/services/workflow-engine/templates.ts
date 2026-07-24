/**
 * 伏羲 v2.1 — 工作流节点模板定义
 *
 * 定义拖拽面板中可用的节点模板
 */

import type { NodeTemplate } from './types';

export const nodeTemplates: NodeTemplate[] = [
  // ───── 触发器 ─────
  {
    type: 'trigger',
    label: '手动触发',
    icon: '🖐',
    category: '触发器',
    defaultConfig: {
      subType: 'manual',
      inputSchema: {},
    },
  },
  {
    type: 'trigger',
    label: 'Webhook',
    icon: '🔗',
    category: '触发器',
    defaultConfig: {
      subType: 'webhook',
      webhookUrl: '',
      inputSchema: {},
    },
  },
  {
    type: 'trigger',
    label: '定时触发',
    icon: '⏰',
    category: '触发器',
    defaultConfig: {
      subType: 'schedule',
      cronExpression: '0 0 * * *',
    },
  },
  {
    type: 'trigger',
    label: '事件触发',
    icon: '⚡',
    category: '触发器',
    defaultConfig: {
      subType: 'event',
      eventName: '',
    },
  },

  // ───── 条件 ─────
  {
    type: 'condition',
    label: '条件判断',
    icon: '◇',
    category: '条件',
    defaultConfig: {
      branches: [],
      defaultBranch: '',
    },
  },

  // ───── 动作 ─────
  {
    type: 'action',
    label: 'API 调用',
    icon: '🌐',
    category: '动作',
    defaultConfig: {
      subType: 'api_call',
      apiUrl: '',
      apiMethod: 'POST',
      apiBody: '{}',
    },
  },
  {
    type: 'action',
    label: '发送通知',
    icon: '📬',
    category: '动作',
    defaultConfig: {
      subType: 'notification',
      notificationMessage: '',
    },
  },
  {
    type: 'action',
    label: '数据转换',
    icon: '🔄',
    category: '动作',
    defaultConfig: {
      subType: 'transform',
      transformScript: '',
    },
  },
  {
    type: 'action',
    label: '执行脚本',
    icon: '📜',
    category: '动作',
    defaultConfig: {
      subType: 'script',
      script: '',
    },
  },
  {
    type: 'action',
    label: '延迟等待',
    icon: '⏳',
    category: '动作',
    defaultConfig: {
      subType: 'delay',
      delayMs: 1000,
    },
  },

  // ───── 循环 ─────
  {
    type: 'loop',
    label: '遍历循环',
    icon: '🔁',
    category: '循环',
    defaultConfig: {
      subType: 'for_each',
      iteratorVar: 'item',
      collectionRef: '',
      maxIterations: 100,
    },
  },
  {
    type: 'loop',
    label: '条件循环',
    icon: '🔄',
    category: '循环',
    defaultConfig: {
      subType: 'while',
      conditionExpression: '',
      maxIterations: 100,
    },
  },
  {
    type: 'loop',
    label: '重复次数',
    icon: '🔢',
    category: '循环',
    defaultConfig: {
      subType: 'repeat',
      repeatCount: 5,
      maxIterations: 100,
    },
  },
];

/**
 * 按类型获取节点模板
 */
export function getTemplatesByType(type: string): NodeTemplate[] {
  return nodeTemplates.filter((t) => t.type === type);
}

/**
 * 获取节点图标
 */
export function getNodeIcon(type: string): string {
  const icons: Record<string, string> = {
    trigger: '⚡',
    condition: '◇',
    action: '⚙',
    loop: '🔁',
  };
  return icons[type] ?? '●';
}

/**
 * 获取节点颜色
 */
export function getNodeColor(type: string): string {
  const colors: Record<string, string> = {
    trigger: '#409eff',
    condition: '#e6a23c',
    action: '#67c23a',
    loop: '#9b59b6',
  };
  return colors[type] ?? '#909399';
}
