import apiClient from './index';

// ── 后端用户格式 ──
export interface AdminUser {
  username: string;
  role: string;
  display_name: string;
  created_at: number;
}

// ── 后端响应 ──
export interface AdminUsersResponse {
  ok: boolean;
  users: AdminUser[];
  total: number;
}

/** 获取用户列表 → GET /api/admin/users */
export function getUsers(): Promise<AdminUsersResponse> {
  return apiClient.get('/api/admin/users') as Promise<AdminUsersResponse>;
}

/** 创建用户 → POST /api/admin/users */
export function createUser(data: Record<string, unknown>) {
  return apiClient.post('/api/admin/users', data);
}

/** 更新用户 → PUT /api/admin/users/{id} */
export function updateUser(id: string, data: Record<string, unknown>) {
  return apiClient.put(`/api/admin/users/${id}`, data);
}

/** 删除用户 → DELETE /api/admin/users/{id} */
export function deleteUser(id: string) {
  return apiClient.delete(`/api/admin/users/${id}`);
}
