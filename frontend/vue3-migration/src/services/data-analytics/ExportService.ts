/**
 * 伏羲 v2.1 — 数据导出服务
 *
 * 提供多格式导出（PDF/Excel/CSV/JSON）、报表模板管理、
 * 分享链接生成和权限控制的业务逻辑封装。
 *
 * 架构角色：API 层和 Store/Component 之间的中间层，
 * 统一处理导出流程、分享验证、缓存策略等。
 */

import { createLogger } from '@/utils/logger';
import type {
  ExportConfig,
  ExportFormat,
  ExportResponse,
  ReportTemplate,
  ShareConfig,
  SharePermission,
  ShareResponse,
  SharedReport,
} from './types';
import * as analyticsApi from './api';

const logger = createLogger('ExportService');

// ───── 常量 ─────

/** 所有可选导出字段 */
export const ALL_EXPORT_FIELDS = [
  { value: 'date', label: '日期' },
  { value: 'queries', label: '查询量' },
  { value: 'documents', label: '文档数' },
  { value: 'users', label: '用户数' },
  { value: 'storage', label: '存储用量' },
  { value: 'vectors', label: '向量数' },
  { value: 'response_time', label: '响应时间' },
  { value: 'success_rate', label: '成功率' },
  { value: 'error_count', label: '错误数' },
  { value: 'avg_tokens', label: '平均Token' },
] as const;

/** 导出格式配置 */
export const EXPORT_FORMAT_CONFIG: Record<
  ExportFormat,
  { label: string; icon: string; extension: string; description: string }
> = {
  pdf: {
    label: 'PDF',
    icon: 'Document',
    extension: '.pdf',
    description: '适合打印和正式汇报',
  },
  excel: {
    label: 'Excel',
    icon: 'Grid',
    extension: '.xlsx',
    description: '适合数据分析和二次处理',
  },
  csv: {
    label: 'CSV',
    icon: 'List',
    extension: '.csv',
    description: '通用格式，兼容性强',
  },
  json: {
    label: 'JSON',
    icon: 'DataBoard',
    extension: '.json',
    description: '适合程序对接和API集成',
  },
} as const;

/** 分享权限配置 */
export const SHARE_PERMISSION_CONFIG: Record<
  SharePermission,
  { label: string; description: string; icon: string }
> = {
  view: {
    label: '查看',
    description: '可以查看报表内容',
    icon: 'View',
  },
  edit: {
    label: '编辑',
    description: '可以修改报表内容',
    icon: 'Edit',
  },
  download: {
    label: '下载',
    description: '可以下载报表数据',
    icon: 'Download',
  },
} as const;

// ───── 服务类 ─────

/**
 * 数据导出服务（单例模式）
 *
 * 职责：
 * - 多格式导出（PDF/Excel/CSV/JSON）
 * - 报表模板 CRUD
 * - 分享链接生成、验证、撤销
 * - 权限控制逻辑
 */
class ExportService {
  /** 变更监听器 */
  private listeners: Array<
    (event: { action: string; payload: unknown }) => void
  > = [];

  // ───── 导出操作 ─────

  /**
   * 导出数据
   *
   * @param config - 导出配置
   * @returns 导出响应（含下载链接）
   */
  async export(config: ExportConfig): Promise<ExportResponse> {
    logger.info(`开始导出: ${config.format}, 字段数: ${config.fields.length}`);

    try {
      // 验证必填字段
      this.validateExportConfig(config);

      const result = await analyticsApi.exportData(config);

      this.notifyListeners('exported', {
        format: config.format,
        filename: result.filename,
        size: result.size,
      });

      // 触发浏览器下载
      this.triggerDownload(result.download_url, result.filename);

      return result;
    } catch (err) {
      logger.error('导出失败', err);
      throw new Error(config.format === 'pdf' ? 'PDF 导出失败，请重试' : '数据导出失败，请重试');
    }
  }

  /**
   * 构建导出配置的默认值
   */
  buildDefaultConfig(format: ExportFormat = 'csv'): ExportConfig {
    return {
      format,
      fields: ALL_EXPORT_FIELDS.slice(0, 6).map((f) => f.value),
      date_range: {},
      title: `数据导出_${new Date().toISOString().slice(0, 10)}`,
    };
  }

  /**
   * 验证导出配置
   */
  private validateExportConfig(config: ExportConfig): void {
    if (!config.fields || config.fields.length === 0) {
      throw new Error('请至少选择一个导出字段');
    }

    if (config.date_range?.start && config.date_range?.end) {
      const start = new Date(config.date_range.start).getTime();
      const end = new Date(config.date_range.end).getTime();
      if (start > end) {
        throw new Error('开始日期不能晚于结束日期');
      }
      // 限制最大范围为 1 年
      const oneYear = 365 * 24 * 60 * 60 * 1000;
      if (end - start > oneYear) {
        throw new Error('时间范围不能超过一年');
      }
    }
  }

  /**
   * 触发浏览器下载
   */
  private triggerDownload(url: string, filename: string): void {
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    anchor.style.display = 'none';
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
  }

  // ───── 模板管理 ─────

  /**
   * 获取所有模板
   */
  async getTemplates(): Promise<ReportTemplate[]> {
    try {
      const templates = await analyticsApi.getTemplates();
      logger.info(`获取模板列表: ${templates.length} 个`);
      return templates;
    } catch (err) {
      logger.error('获取模板失败', err);
      return [];
    }
  }

  /**
   * 创建模板
   */
  async createTemplate(
    data: Omit<ReportTemplate, 'id' | 'created_at' | 'updated_at'>,
  ): Promise<ReportTemplate | null> {
    try {
      const template = await analyticsApi.createTemplate(data);
      logger.info(`模板已创建: ${template.name}`);
      this.notifyListeners('template_created', template);
      return template;
    } catch (err) {
      logger.error('创建模板失败', err);
      return null;
    }
  }

  /**
   * 更新模板
   */
  async updateTemplate(
    id: string,
    data: Partial<ReportTemplate>,
  ): Promise<ReportTemplate | null> {
    try {
      const template = await analyticsApi.updateTemplate(id, data);
      logger.info(`模板已更新: ${template.name}`);
      return template;
    } catch (err) {
      logger.error('更新模板失败', err);
      return null;
    }
  }

  /**
   * 删除模板
   */
  async deleteTemplate(id: string): Promise<boolean> {
    try {
      await analyticsApi.deleteTemplate(id);
      logger.info(`模板已删除: ${id}`);
      this.notifyListeners('template_deleted', { id });
      return true;
    } catch (err) {
      logger.error('删除模板失败', err);
      return false;
    }
  }

  // ───── 分享管理 ─────

  /**
   * 生成分享链接
   *
   * @param config - 分享配置
   * @returns 分享响应（含链接和 token）
   */
  async shareReport(config: ShareConfig): Promise<ShareResponse | null> {
    logger.info(`生成分享链接: report_id=${config.report_id}`);

    try {
      this.validateShareConfig(config);
      const result = await analyticsApi.shareReport(config);
      this.notifyListeners('shared', result);
      return result;
    } catch (err) {
      logger.error('分享失败', err);
      return null;
    }
  }

  /**
   * 通过 token 获取分享的报表
   *
   * @param token - 访问令牌
   * @returns 分享的报表（含权限校验结果）
   */
  async getSharedReport(token: string): Promise<SharedReport | null> {
    try {
      const report = await analyticsApi.getSharedReport(token);
      logger.info(`获取分享报表: ${report.title}`);
      return report;
    } catch (err) {
      logger.error('获取分享报表失败', err);
      return null;
    }
  }

  /**
   * 撤销分享
   *
   * @param token - 分享令牌
   */
  async revokeShare(token: string): Promise<boolean> {
    try {
      await analyticsApi.revokeShare(token);
      logger.info(`分享已撤销: ${token}`);
      this.notifyListeners('share_revoked', { token });
      return true;
    } catch (err) {
      logger.error('撤销分享失败', err);
      return false;
    }
  }

  /**
   * 检查用户是否有指定权限
   *
   * @param report - 共享报表
   * @param requiredPermission - 需要的权限
   */
  hasPermission(report: SharedReport, requiredPermission: SharePermission): boolean {
    return report.permissions.includes(requiredPermission);
  }

  /**
   * 验证分享配置
   */
  private validateShareConfig(config: ShareConfig): void {
    if (!config.report_id) {
      throw new Error('报表 ID 不能为空');
    }
    if (!config.permissions || config.permissions.length === 0) {
      throw new Error('请至少选择一种分享权限');
    }
    if (config.expires_at) {
      const expiresAt = new Date(config.expires_at).getTime();
      if (expiresAt <= Date.now()) {
        throw new Error('过期时间必须在当前时间之后');
      }
      // 限制最长期限为 30 天
      const maxExpiry = Date.now() + 30 * 24 * 60 * 60 * 1000;
      if (expiresAt > maxExpiry) {
        throw new Error('分享有效期不能超过 30 天');
      }
    }
  }

  /**
   * 复制文本到剪贴板
   */
  async copyToClipboard(text: string): Promise<boolean> {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // 降级方案
      const textarea = document.createElement('textarea');
      textarea.value = text;
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      const success = document.execCommand('copy');
      document.body.removeChild(textarea);
      return success;
    }
  }

  // ───── 事件监听 ─────

  /**
   * 注册变更监听器
   *
   * @param listener - 事件处理函数
   * @returns 取消订阅的函数
   */
  onChange(listener: (event: { action: string; payload: unknown }) => void): () => void {
    this.listeners.push(listener);
    return () => {
      const idx = this.listeners.indexOf(listener);
      if (idx > -1) this.listeners.splice(idx, 1);
    };
  }

  private notifyListeners(action: string, payload: unknown): void {
    for (const listener of this.listeners) {
      try {
        listener({ action, payload });
      } catch (err) {
        logger.error('Listener 执行异常', err);
      }
    }
  }
}

// ───── 单例导出 ─────

export const exportService = new ExportService();
export default exportService;
