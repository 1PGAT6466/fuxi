/**
 * 伏羲 v2.1 — 数据分析 Mock 数据
 * 提供 API 不可用时的兜底 mock 响应
 */

import type {
  StatsResponse,
  TrendsResponse,
  TrendPeriod,
  StorageDistResponse,
  ReportResponse,
  ReportRequest,
  ExportResponse,
  ExportConfig,
} from './types';

// ───── 随机工具函数 ─────

function rand(min: number, max: number): number {
  return +(min + Math.random() * (max - min)).toFixed(1);
}

function randInt(min: number, max: number): number {
  return Math.floor(rand(min, max));
}

function genTrend(seed: number, count: number, variance: number): number[] {
  let v = seed;
  return Array.from({ length: count }, () => {
    v += rand(-variance, variance);
    return Math.max(0, +v.toFixed(0));
  });
}

function daysAgo(n: number, base = new Date()): string {
  const d = new Date(base);
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}

// ───── Mock 响应生成函数 ─────

export const mockAnalyticsResponse = {
  /** 统计概览 */
  stats(): StatsResponse {
    return {
      updated_at: new Date().toISOString(),
      stats: [
        {
          label: '文档总数',
          value: 125834 + randInt(-500, 500),
          unit: '篇',
          change: 12.5,
          trend: genTrend(120000, 7, 2000),
        },
        {
          label: '用户数',
          value: 3842 + randInt(-20, 20),
          unit: '人',
          change: 8.3,
          trend: genTrend(3700, 7, 20),
        },
        {
          label: '向量总数',
          value: 2156000 + randInt(-10000, 10000),
          unit: '条',
          change: 24.7,
          trend: genTrend(2000000, 7, 30000),
        },
        {
          label: '存储用量',
          value: 456.8 + rand(-5, 5),
          unit: 'GB',
          change: 15.2,
          trend: genTrend(380, 7, 12),
        },
      ],
    };
  },

  /** 趋势分析 */
  trends(period: TrendPeriod): TrendsResponse {
    const count = period === 'day' ? 24 : period === 'week' ? 7 : 30;
    const points = Array.from({ length: count }, (_, i) => {
      const d = period === 'day' ? `${i.toString().padStart(2, '0')}:00` : daysAgo(count - 1 - i);
      return {
        date: d,
        queries: randInt(800, 3500),
        documents: randInt(50, 300),
        active_users: randInt(200, 800),
      };
    });

    return { period, data: points };
  },

  /** 存储分布 */
  storageDist(): StorageDistResponse {
    return {
      by_file_type: [
        { type: 'pdf', label: 'PDF 文档', size: 186.2, count: 45230 },
        { type: 'docx', label: 'Word 文档', size: 98.7, count: 31200 },
        { type: 'txt', label: '纯文本', size: 45.3, count: 28000 },
        { type: 'image', label: '图片', size: 72.1, count: 15400 },
        { type: 'other', label: '其他', size: 54.5, count: 6004 },
      ],
      by_collection: [
        { collection: '技术文档', size: 128.5, document_count: 25000, vector_count: 520000 },
        { collection: '产品手册', size: 95.2, document_count: 18000, vector_count: 380000 },
        { collection: '规章制度', size: 62.8, document_count: 22000, vector_count: 420000 },
        { collection: '培训材料', size: 88.3, document_count: 31000, vector_count: 480000 },
        { collection: '研究报告', size: 45.6, document_count: 12000, vector_count: 200000 },
        { collection: '新闻资讯', size: 36.4, document_count: 17834, vector_count: 156000 },
      ],
    };
  },

  /** 报表生成 */
  report(req: ReportRequest): ReportResponse {
    const sections = req.dimensions.map((dim) => {
      const dimMap: Record<string, { title: string; content: string }> = {
        queries: {
          title: '查询分析',
          content: `在 ${req.period} 周期内，系统共处理查询 ${randInt(50000, 200000)} 次，平均响应时间 ${rand(120, 450)}ms。查询成功率 ${rand(98, 99.9).toFixed(1)}%，Top 5 高频查询词为：数据分析、文档格式、向量检索、知识图谱、智能推荐。`,
        },
        documents: {
          title: '文档分析',
          content: `本周期内新增文档 ${randInt(500, 5000)} 篇，活跃文档 ${randInt(10000, 50000)} 篇。文档类型分布：PDF ${rand(35, 45)}%，Word ${rand(20, 30)}%，文本 ${rand(10, 20)}%，其他 ${rand(5, 15)}%。`,
        },
        users: {
          title: '用户分析',
          content: `活跃用户 ${randInt(500, 2000)} 人，新增用户 ${randInt(50, 200)} 人。用户平均使用时长 ${rand(15, 45)} 分钟，日活率 ${rand(20, 40).toFixed(1)}%。`,
        },
        storage: {
          title: '存储分析',
          content: `总存储用量 ${rand(400, 500).toFixed(1)} GB，环比增长 ${rand(5, 20).toFixed(1)}%。PDF 文件占比最高 ${rand(35, 45)}%，图片存储增长较快 ${rand(8, 15).toFixed(1)}%。`,
        },
        vectors: {
          title: '向量分析',
          content: `向量总数 ${rand(2000000, 2200000)}，本周新增 ${randInt(10000, 50000)} 条向量。平均向量维度 1536，检索平均耗时 ${rand(5, 20)}ms，Top-K 召回率 ${rand(90, 98).toFixed(1)}%。`,
        },
      };
      const info = dimMap[dim] || { title: dim, content: '暂无数据' };
      return {
        title: info.title,
        content: info.content,
        metrics: {
          avg_value: rand(100, 1000),
          peak_value: rand(500, 5000),
          growth_rate: rand(5, 25),
        },
      };
    });

    return {
      id: `rpt_${Date.now()}`,
      type: req.type,
      title: req.type === 'summary' ? `摘要报表 — ${req.period}` : `详细报表 — ${req.period}`,
      generated_at: new Date().toISOString(),
      period: req.period,
      sections,
    };
  },

  /** 导出数据 */
  exportData(config: ExportConfig): ExportResponse {
    const ext = config.format === 'csv' ? 'csv' : 'xlsx';
    return {
      download_url: `/api/analytics/export/download/${config.format}_${Date.now()}.${ext}`,
      filename: `analytics_export_${new Date().toISOString().slice(0, 10)}.${ext}`,
      format: config.format,
      size: randInt(50000, 5000000),
    };
  },
};
