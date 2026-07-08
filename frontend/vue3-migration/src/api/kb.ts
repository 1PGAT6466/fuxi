import apiClient from './index';

export function searchKB(query: string) {
  return apiClient.post('/api/kb/search', { query });
}

export function getKBDocuments() {
  return apiClient.get('/api/kb/documents');
}
