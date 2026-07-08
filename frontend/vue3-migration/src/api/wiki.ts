import apiClient from './index';

export function getWikiPages() {
  return apiClient.get('/api/wiki');
}

export function getWikiPage(id: string) {
  return apiClient.get(`/api/wiki/${id}`);
}

export function createWikiPage(data: any) {
  return apiClient.post('/api/wiki', data);
}

export function updateWikiPage(id: string, data: any) {
  return apiClient.put(`/api/wiki/${id}`, data);
}
