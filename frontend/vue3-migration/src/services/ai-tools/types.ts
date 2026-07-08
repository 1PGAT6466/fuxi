/**
 * 伏羲 v2.1 — AI 工具集类型定义
 */

// ───── 健康检查 ─────

export interface AiHealthResponse {
  status: 'ok' | 'degraded' | 'error';
  version: string;
  models_available: string[];
  uptime_seconds: number;
}

// ───── 文本摘要 ─────

export interface SummarizeRequest {
  text: string;
  max_length?: 'short' | 'medium' | 'long';
}

export interface SummarizeResponse {
  summary: string;
  original_length: number;
  summary_length: number;
  compression_ratio: number;
}

// ───── 智能翻译 ─────

export interface TranslateRequest {
  text: string;
  source_lang: string;
  target_lang: string;
}

export interface TranslateResponse {
  translated_text: string;
  source_lang: string;
  target_lang: string;
  confidence: number;
}

// ───── 关键词提取 ─────

export interface KeywordItem {
  keyword: string;
  weight: number; // 0-1
}

export interface KeywordsResponse {
  keywords: KeywordItem[];
}

// ───── 实体识别 ─────

export interface EntityItem {
  name: string;
  type: string;
  description?: string;
  start_pos?: number;
  end_pos?: number;
}

export interface EntitiesResponse {
  entities: EntityItem[];
}

// ───── 文本分类 ─────

export interface ClassificationResult {
  category: string;
  confidence: number; // 0-1
}

export interface ClassifyRequest {
  text: string;
  categories?: string[];
}

export interface ClassifyResponse {
  results: ClassificationResult[];
}
