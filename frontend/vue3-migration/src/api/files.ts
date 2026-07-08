import apiClient from './index';

export function fetchFiles(params?: Record<string, unknown>) {
  return apiClient.get('/api/files', params ? { params } : undefined);
}

export function uploadFile(data: FormData) {
  return apiClient.post('/api/files/upload', data);
}

export function deleteFile(id: string) {
  return apiClient.delete(`/api/files/${id}`);
}

export function downloadFile(id: string) {
  return apiClient.get(`/api/files/${id}/download`, { responseType: 'blob' });
}
