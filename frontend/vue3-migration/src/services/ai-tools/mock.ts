/**
 * 伏羲 v2.1 — AI 工具集 Mock 数据
 * 提供 API 不可用时的兜底 mock 响应
 */

import type {
  AiHealthResponse,
  SummarizeResponse,
  TranslateResponse,
  KeywordsResponse,
  EntitiesResponse,
  ClassifyResponse,
} from './types';

// ───── 多语言文本数据集（mock 用） ─────

const MOCK_TEXT_CN =
  '人工智能技术正在深刻改变着我们的生活方式。从智能手机上的语音助手，到自动驾驶汽车，再到医疗影像诊断，AI的应用已经无处不在。深度学习、自然语言处理和计算机视觉等技术的突破，让机器能够完成越来越多过去只有人类才能完成的任务。随着算力的不断提升和数据量的爆炸式增长，未来AI将在更多领域发挥关键作用。';

const MOCK_TEXT_EN =
  'Artificial intelligence is profoundly transforming the way we live. From voice assistants on smartphones to autonomous vehicles and medical image diagnostics, AI applications are everywhere. Breakthroughs in deep learning, natural language processing, and computer vision enable machines to accomplish an increasing number of tasks that were once exclusive to humans.';

// ───── Mock 响应生成函数 ─────

export const mockAiToolsResponse = {
  /** 健康检查 */
  health(): AiHealthResponse {
    return {
      status: 'ok',
      version: '2.1.0-mock',
      models_available: ['gpt-4o', 'deepseek-v4', 'qwen-max'],
      uptime_seconds: 86400 + (Math.floor(Date.now() / 1000) % 3600),
    };
  },

  /** 文本摘要 */
  summarize(text: string, maxLength?: string): SummarizeResponse {
    const lengthMap: Record<string, string> = {
      short: 'AI技术正在改变生活方式，在语音助手、自动驾驶、医疗诊断等领域广泛应用。',
      medium:
        '人工智能技术正在深刻改变生活方式。从语音助手到自动驾驶，再到医疗诊断，AI应用无处不在。深度学习等技术突破让机器能完成越来越多人类任务。',
      long: '人工智能技术正在深刻改变我们的生活方式，应用涵盖智能手机语音助手、自动驾驶汽车、医疗影像诊断等各个领域。深度学习、自然语言处理和计算机视觉等技术突破，让机器能够完成越来越多过去只有人类才能完成的任务。随着算力提升和数据增长，AI将在更多领域发挥关键作用。',
    };
    const summary = lengthMap[maxLength || 'medium'] || lengthMap.medium;
    return {
      summary,
      original_length: text.length || MOCK_TEXT_CN.length,
      summary_length: summary.length,
      compression_ratio: parseFloat(
        ((summary.length / (text.length || MOCK_TEXT_CN.length)) * 100).toFixed(1),
      ),
    };
  },

  /** 智能翻译 */
  translate(text: string, sourceLang: string, targetLang: string): TranslateResponse {
    const commonWords: Record<string, string> = {
      你好: 'Hello',
      谢谢: 'Thank you',
      人工智能: 'Artificial Intelligence',
      深度学习: 'Deep Learning',
    };

    let translated = text;
    if (sourceLang === 'zh' && targetLang === 'en') {
      translated = MOCK_TEXT_EN;
      for (const [zh, en] of Object.entries(commonWords)) {
        if (text.includes(zh)) translated = en;
      }
    } else if (sourceLang === 'en' && targetLang === 'zh') {
      translated = MOCK_TEXT_CN;
      for (const [zh, en] of Object.entries(commonWords)) {
        if (text.includes(en)) translated = zh;
      }
    } else if (sourceLang === 'zh' && targetLang === 'ja') {
      translated =
        '人工知能技術は私たちの生活様式を大きく変えています。スマートフォンの音声アシスタントから自動運転車、医療画像診断まで、AIの応用は至る所にあります。';
    }

    return {
      translated_text: translated || text,
      source_lang: sourceLang,
      target_lang: targetLang,
      confidence: 0.95,
    };
  },

  /** 关键词提取 */
  keywords(_text: string): KeywordsResponse {
    return {
      keywords: [
        { keyword: '人工智能', weight: 0.95 },
        { keyword: '深度学习', weight: 0.88 },
        { keyword: '自然语言处理', weight: 0.82 },
        { keyword: '计算机视觉', weight: 0.78 },
        { keyword: '自动驾驶', weight: 0.72 },
        { keyword: '语音助手', weight: 0.68 },
        { keyword: '医疗影像', weight: 0.65 },
        { keyword: '算力', weight: 0.55 },
        { keyword: '神经网络', weight: 0.48 },
        { keyword: '大数据', weight: 0.42 },
      ],
    };
  },

  /** 实体识别 */
  entities(_text: string): EntitiesResponse {
    return {
      entities: [
        {
          name: '人工智能',
          type: '技术领域',
          description: 'Artificial Intelligence，计算机科学的一个分支',
          start_pos: 0,
          end_pos: 4,
        },
        {
          name: '智能手机',
          type: '产品类别',
          description: '具备独立操作系统的移动电话',
          start_pos: 20,
          end_pos: 24,
        },
        {
          name: '自动驾驶',
          type: '技术领域',
          description: '车辆在无人工干预下自主行驶的技术',
          start_pos: 30,
          end_pos: 34,
        },
        {
          name: '医疗影像',
          type: '应用领域',
          description: '医学诊断中的图像分析技术',
          start_pos: 38,
          end_pos: 42,
        },
        {
          name: '深度学习',
          type: '技术方法',
          description: 'Deep Learning，多层神经网络学习算法',
          start_pos: 48,
          end_pos: 52,
        },
        {
          name: '自然语言处理',
          type: '技术方法',
          description: 'NLP，计算机理解人类语言的技术',
          start_pos: 54,
          end_pos: 60,
        },
        {
          name: '计算机视觉',
          type: '技术方法',
          description: 'CV，让机器"看懂"图像的技术',
          start_pos: 62,
          end_pos: 66,
        },
      ],
    };
  },

  /** 文本分类 */
  classify(_text: string, _categories?: string[]): ClassifyResponse {
    return {
      results: [
        { category: '科技/AI', confidence: 0.92 },
        { category: '科技/计算机科学', confidence: 0.78 },
        { category: '商业/数字化转型', confidence: 0.45 },
        { category: '教育/科普', confidence: 0.38 },
        { category: '医疗/医学影像', confidence: 0.22 },
      ],
    };
  },
};
