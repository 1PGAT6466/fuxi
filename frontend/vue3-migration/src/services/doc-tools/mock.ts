/**
 * 伏羲 v2.1 — 文档工具 Mock 数据
 * 提供 API 不可用时的兜底 mock 响应
 */

import type {
  ConvertResponse,
  MergeResponse,
  SplitResponse,
  CompressResult,
  ImageMeta,
  TextExtractResult,
  CompressOptions,
} from './types';

// ───── 随机工具 ─────

function randInt(min: number, max: number): number {
  return Math.floor(min + Math.random() * (max - min));
}

function randDelay(): Promise<void> {
  return new Promise((r) => setTimeout(r, 500 + Math.random() * 1500));
}

// ───── 文件大小格式化 ─────

function formatSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  return (bytes / 1024).toFixed(1) + ' KB';
}

// ───── Mock 响应 ─────

export const mockDocToolsResponse = {
  /** 格式转换 */
  async convert(_file: File, targetFormat: string): Promise<ConvertResponse> {
    await randDelay();
    const extMap: Record<string, string> = {
      pdf: '.pdf',
      docx: '.docx',
      doc: '.doc',
      txt: '.txt',
      png: '.png',
      jpg: '.jpg',
      webp: '.webp',
    };
    const srcName = _file.name.replace(/\.[^.]+$/, '');
    return {
      id: `cnv_${Date.now()}`,
      status: 'completed',
      progress: 100,
      source_filename: _file.name,
      target_filename: `${srcName}_converted${extMap[targetFormat] || '.' + targetFormat}`,
      download_url: `/mock/download/${srcName}_converted${extMap[targetFormat] || '.' + targetFormat}`,
    };
  },

  /** PDF 合并 */
  async mergePdfs(files: File[]): Promise<MergeResponse> {
    await randDelay();
    const totalPages = files.length * randInt(3, 15);
    return {
      id: `mrg_${Date.now()}`,
      status: 'completed',
      progress: 100,
      filename: `merged_${Date.now()}.pdf`,
      download_url: `/mock/download/merged_${Date.now()}.pdf`,
      page_count: totalPages,
    };
  },

  /** PDF 拆分 */
  async splitPdf(_file: File, startPage: number, endPage: number): Promise<SplitResponse> {
    await randDelay();
    const parts = [];
    const partCount = Math.max(1, endPage - startPage + 1);
    for (let i = 0; i < partCount; i++) {
      parts.push({
        range: `${startPage + i}`,
        filename: `split_part_${i + 1}.pdf`,
        page_count: 1,
        download_url: `/mock/download/split_part_${i + 1}.pdf`,
      });
    }
    return {
      id: `spl_${Date.now()}`,
      status: 'completed',
      parts,
    };
  },

  /** 文件/图片压缩 */
  async compressFile(file: File, options: CompressOptions): Promise<CompressResult> {
    await randDelay();
    const qualityRatio: Record<string, number> = {
      high: 0.85,
      medium: 0.6,
      low: 0.35,
    };
    const ratio = qualityRatio[options.quality] || 0.6;
    const originalSize = file.size;
    const compressedSize = Math.floor(originalSize * ratio);
    return {
      original_size: originalSize,
      compressed_size: compressedSize,
      ratio: parseFloat(((1 - ratio) * 100).toFixed(1)),
      preview_url: undefined,
      download_url: `/mock/download/compressed_${file.name}`,
    };
  },

  /** 图片元数据 */
  async getImageInfo(file: File): Promise<ImageMeta> {
    await randDelay();
    return {
      width: randInt(800, 4096),
      height: randInt(600, 3072),
      format: file.name.split('.').pop()?.toUpperCase() || 'PNG',
      dpi: 72,
      exif: {
        Make: 'Xiaomi',
        Model: 'Mi 15 Ultra',
        DateTimeOriginal: new Date().toISOString(),
        ISO: String(randInt(100, 6400)),
        FNumber: `f/${randInt(14, 56) / 10}`,
        ExposureTime: `1/${randInt(30, 2000)}`,
        FocalLength: `${randInt(24, 120)}mm`,
        Flash: 'No Flash',
      },
      file_size: file.size,
      aspect_ratio: '16:9',
      color_space: 'sRGB',
      filename: file.name,
    };
  },

  /** 文本提取 */
  async extractText(_file: File): Promise<TextExtractResult> {
    await randDelay();
    const text =
      '人工智能技术正在深刻改变着我们的生活方式。从智能手机上的语音助手，到自动驾驶汽车，再到医疗影像诊断，AI的应用已经无处不在。\n\n' +
      '深度学习、自然语言处理和计算机视觉等技术的突破，让机器能够完成越来越多过去只有人类才能完成的任务。\n\n' +
      '随着算力的不断提升和数据量的爆炸式增长，未来AI将在更多领域发挥关键作用。';
    return {
      text,
      page_count: randInt(1, 20),
      char_count: text.length,
      language: 'zh-CN',
    };
  },
};
