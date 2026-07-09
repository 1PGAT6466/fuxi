import apiClient from './index';

export interface BackendFileInfo {
  file_name: string;
  file_hash: string;
  category?: { category: string; confidence: number; candidates: string };
  chunk_count: number;
}

export interface FilesListResponse {
  files: BackendFileInfo[];
  total: number;
  page: number;
  page_size: number;
}

/** 获取文件列表 → GET /api/files */
export function fetchFiles(params?: Record<string, unknown>): Promise<FilesListResponse> {
  return apiClient.get('/api/files', params ? { params } : undefined) as Promise<FilesListResponse>;
}

/** 上传文件 → POST /api/files/upload */
export function uploadFile(data: FormData) {
  return apiClient.post('/api/files/upload', data);
}

/** 删除文件 → DELETE /api/files/{id} */
export function deleteFile(id: string) {
  return apiClient.delete(`/api/files/${id}`);
}

/** 下载文件 → GET /api/files/{id}/download */
export function downloadFile(id: string) {
  return apiClient.get(`/api/files/${id}/download`, { responseType: 'blob' });
}
