/**
 * 伏羲 v2.1 — 用户反馈 API
 * 对接后端 /api/feedback、/api/feedback/weekly
 */

import apiClient from './index';

export interface WeeklyFeedback {
  feedbacks: Array<{
    id?: string;
    content: string;
    rating?: number;
    created_at?: string;
  }>;
}

export interface FeedbackSubmitParams {
  content: string;
  rating?: number;
  category?: string;
}

export interface FeedbackSubmitResponse {
  ok: boolean;
}

/** 获取每周反馈汇总 */
export async function fetchWeeklyFeedback(): Promise<WeeklyFeedback> {
  return apiClient.get('/api/feedback/weekly') as Promise<WeeklyFeedback>;
}

/** 提交用户反馈 */
export async function submitFeedback(params: FeedbackSubmitParams): Promise<FeedbackSubmitResponse> {
  return apiClient.post('/api/feedback', params) as Promise<FeedbackSubmitResponse>;
}
