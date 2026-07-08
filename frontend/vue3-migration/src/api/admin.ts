import apiClient from './index';

export function getUsers() {
  return apiClient.get('/api/admin/users');
}

export function createUser(data: any) {
  return apiClient.post('/api/admin/users', data);
}

export function updateUser(id: string, data: any) {
  return apiClient.put(`/api/admin/users/${id}`, data);
}

export function deleteUser(id: string) {
  return apiClient.delete(`/api/admin/users/${id}`);
}
