/**
 * 伏羲 v2.1 — DXF 查看器 API 封装
 * 封装 5 个端点：health / files / upload / renderData / download
 * Mock 兜底：API 不可用时使用内置 mock 数据
 */

import apiClient from '@/api';
import { mockDxfResponse } from './mock';
import type { DxfHealthResponse, DxfFile, DxfRenderData } from './types';

// ───── 常量 ─────

const API_BASE = '/api/dxf';

// ───── 通用 mock 兜底请求 ─────

async function requestWithFallback<T>(
  endpoint: string,
  mockData: T,
  method: 'GET' | 'POST' = 'GET',
  body?: unknown,
  isFormData = false,
): Promise<T> {
  try {
    if (method === 'GET') {
      return (await apiClient.get(`${API_BASE}${endpoint}`)) as T;
    }
    if (isFormData) {
      return (await apiClient.post(`${API_BASE}${endpoint}`, body, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })) as T;
    }
    return (await apiClient.post(`${API_BASE}${endpoint}`, body)) as T;
  } catch (err) {
    console.warn(`[DXF Viewer] API ${API_BASE}${endpoint} 不可用，使用 mock 数据`, err);
    return mockData;
  }
}

// ───── 端点封装 ─────

/** 健康检查 */
export async function healthCheck(): Promise<DxfHealthResponse> {
  return requestWithFallback<DxfHealthResponse>('/health', mockDxfResponse.health());
}

/** 获取 DXF 文件列表 */
export async function listFiles(): Promise<DxfFile[]> {
  return requestWithFallback<DxfFile[]>('/files', mockDxfResponse.listFiles());
}

/** 上传 DXF 文件 */
export async function uploadDxf(file: File): Promise<{ file_id: string; hash: string }> {
  try {
    const formData = new FormData();
    formData.append('file', file);
    return (await apiClient.post(`${API_BASE}/files/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })) as { file_id: string; hash: string };
  } catch (err) {
    console.warn('[DXF Viewer] 上传 API 不可用，使用 mock 数据', err);
    // Mock 上传：返回一个模拟的 hash
    const mockHash = `dxf_mock_${Date.now()}`;
    return { file_id: mockHash, hash: mockHash };
  }
}

/** 获取 DXF 渲染数据（几何实体 + 图层） */
export async function getRenderData(hash: string): Promise<DxfRenderData> {
  // 模拟 300ms 网络延迟使加载状态可见
  const mockData = mockDxfResponse.getRenderData(hash);
  try {
    const result = await apiClient.get(`${API_BASE}/files/${hash}/render`);
    return result as DxfRenderData;
  } catch (err) {
    console.warn(`[DXF Viewer] 渲染数据 API 不可用，使用 mock 数据`, err);
    // 模拟延迟
    await new Promise((resolve) => setTimeout(resolve, 300));
    return mockData;
  }
}

/** 下载 DXF 文件 */
export async function downloadDxf(hash: string): Promise<Blob | null> {
  try {
    const response = await apiClient.get(`${API_BASE}/files/${hash}/download`, {
      responseType: 'blob',
    });
    return response as unknown as Blob;
  } catch (err) {
    console.warn('[DXF Viewer] 下载 API 不可用', err);
    return null;
  }
}
