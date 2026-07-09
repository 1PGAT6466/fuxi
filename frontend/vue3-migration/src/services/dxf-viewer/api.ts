/**
 * 伏羲 v2.1 — DXF 查看器 API 封装
 * 封装 5 个端点：health / files / upload / renderData / download
 * 数据来源：后端 API，失败时抛出错误，不返回兜底 mock
 */

import apiClient from '@/api';
import type { DxfHealthResponse, DxfFile, DxfRenderData } from './types';

// ───── 常量 ─────

const API_BASE = '/api/dxf';

// ───── 端点封装 ─────

/** 健康检查 */
export async function healthCheck(): Promise<DxfHealthResponse> {
  return apiClient.get(`${API_BASE}/health`) as Promise<DxfHealthResponse>;
}

/** 获取 DXF 文件列表 */
export async function listFiles(): Promise<DxfFile[]> {
  return apiClient.get(`${API_BASE}/files`) as Promise<DxfFile[]>;
}

/** 上传 DXF 文件 */
export async function uploadDxf(file: File): Promise<{ file_id: string; hash: string }> {
  const formData = new FormData();
  formData.append('file', file);
  return apiClient.post(`${API_BASE}/files/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }) as Promise<{ file_id: string; hash: string }>;
}

/** 获取 DXF 渲染数据（几何实体 + 图层） */
export async function getRenderData(hash: string): Promise<DxfRenderData> {
  return apiClient.get(`${API_BASE}/files/${hash}/render`) as Promise<DxfRenderData>;
}

/** 下载 DXF 文件 */
export async function downloadDxf(hash: string): Promise<Blob | null> {
  try {
    const response = await apiClient.get(`${API_BASE}/files/${hash}/download`, {
      responseType: 'blob',
    });
    return response as unknown as Blob;
  } catch {
    return null;
  }
}
