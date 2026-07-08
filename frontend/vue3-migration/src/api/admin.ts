import apiClient from './index';

export function getUsers() {
  return apiClient.get('/api/admin/users');
}

export function createUser(data: Record<string, unknown>) {
  return apiClient.post('/api/admin/users', data);
}

export function updateUser(id: string, data: Record<string, unknown>) {
  return apiClient.put(`/api/admin/users/${id}`, data);
}

export function deleteUser(id: string) {
  return apiClient.delete(`/api/admin/users/${id}`);
}
