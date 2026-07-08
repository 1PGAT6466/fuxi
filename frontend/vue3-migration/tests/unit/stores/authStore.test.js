/**
 * authStore 测试
 * 测试登录、登出和用户信息获取
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';

// Mock API client
const mockApiClient = {
  post: vi.fn(),
  get: vi.fn(),
};

vi.mock('@/api', () => ({
  default: mockApiClient,
}));

describe('authStore', () => {
  let authStore;

  beforeEach(async () => {
    setActivePinia(createPinia());
    localStorage.clear();
    mockApiClient.post.mockReset();
    mockApiClient.get.mockReset();

    // 使用动态 import 以确保路径别名正确解析
    const { useAuthStore } = await import('@/stores/auth');
    authStore = useAuthStore();
  });

  describe('初始状态', () => {
    it('初始 token 为空字符串', () => {
      expect(authStore.token).toBe('');
    });

    it('初始 user 为 null', () => {
      expect(authStore.user).toBeNull();
    });

    it('初始 loading 为 false', () => {
      expect(authStore.loading).toBe(false);
    });

    it('初始 isAuthenticated 为 false', () => {
      expect(authStore.isAuthenticated).toBe(false);
    });

    it('初始 isAdmin 为 false', () => {
      expect(authStore.isAdmin).toBe(false);
    });
  });

  describe('login', () => {
    it('成功登录应设置 token 和 user', async () => {
      const mockResponse = {
        token: 'test-token-abc123',
        user: { id: 1, username: 'admin', role: 'admin' },
      };
      mockApiClient.post.mockResolvedValueOnce(mockResponse);

      const result = await authStore.login('admin', 'password123');

      expect(authStore.token).toBe('test-token-abc123');
      expect(authStore.user).toEqual(mockResponse.user);
      expect(authStore.isAuthenticated).toBe(true);
      expect(authStore.isAdmin).toBe(true);
      expect(result).toEqual(mockResponse);
    });

    it('登录时应保存 token 到 localStorage', async () => {
      mockApiClient.post.mockResolvedValueOnce({
        token: 'stored-token',
        user: { id: 2, username: 'user', role: 'user' },
      });

      await authStore.login('user', 'pass');

      expect(localStorage.getItem('fuxi-token')).toBe('stored-token');
    });

    it('登录时应调用正确的 API', async () => {
      mockApiClient.post.mockResolvedValueOnce({
        token: 'tk',
        user: { id: 1 },
      });

      await authStore.login('testuser', 'testpass');

      expect(mockApiClient.post).toHaveBeenCalledWith('/api/auth/login', {
        username: 'testuser',
        password: 'testpass',
      });
    });

    it('非管理员用户 isAdmin 为 false', async () => {
      mockApiClient.post.mockResolvedValueOnce({
        token: 'tk',
        user: { id: 2, username: 'normal', role: 'user' },
      });

      await authStore.login('normal', 'pass');

      expect(authStore.isAdmin).toBe(false);
    });

    it('登录失败时应抛出错误', async () => {
      mockApiClient.post.mockRejectedValueOnce(new Error('登录失败'));

      await expect(authStore.login('user', 'wrong')).rejects.toThrow('登录失败');
    });

    it('无论登录成功与否，loading 应恢复 false', async () => {
      mockApiClient.post.mockRejectedValueOnce(new Error('fail'));

      await authStore.login('u', 'p').catch(() => {});
      expect(authStore.loading).toBe(false);
    });
  });

  describe('logout', () => {
    it('登出应清除 token 和 user', async () => {
      // 先登录
      mockApiClient.post.mockResolvedValueOnce({
        token: 'tk',
        user: { id: 1, username: 'admin' },
      });
      await authStore.login('admin', 'pass');

      // 然后登出
      authStore.logout();

      expect(authStore.token).toBe('');
      expect(authStore.user).toBeNull();
      expect(authStore.isAuthenticated).toBe(false);
    });

    it('登出应移除 localStorage 中的 token', async () => {
      mockApiClient.post.mockResolvedValueOnce({
        token: 'tk',
        user: { id: 1 },
      });
      await authStore.login('u', 'p');

      authStore.logout();

      expect(localStorage.getItem('fuxi-token')).toBeNull();
    });
  });

  describe('fetchUser', () => {
    it('成功获取用户信息应设置 user', async () => {
      const userData = { id: 1, username: 'admin', role: 'admin' };
      mockApiClient.get.mockResolvedValueOnce({ data: userData });

      const result = await authStore.fetchUser();

      expect(authStore.user).toEqual(userData);
      expect(result).toEqual(userData);
    });

    it('获取用户信息时应调用正确的 API', async () => {
      mockApiClient.get.mockResolvedValueOnce({ data: { id: 1 } });

      await authStore.fetchUser();

      expect(mockApiClient.get).toHaveBeenCalledWith('/api/auth/me');
    });

    it('获取失败时应登出并抛出错误', async () => {
      // 先设置一个 token
      localStorage.setItem('token', 'existing-token');
      mockApiClient.get.mockRejectedValueOnce(new Error('Unauthorized'));

      await expect(authStore.fetchUser()).rejects.toThrow('获取用户信息失败');

      expect(authStore.token).toBe('');
      expect(authStore.user).toBeNull();
    });
  });

  describe('localStorage token 持久化', () => {
    it('如果 localStorage 中有 token，初始化时应加载', async () => {
      localStorage.setItem('token', 'persisted-token');

      // 重新创建 store（需要先用新的 pinia）
      setActivePinia(createPinia());
      const { useAuthStore } = await import('@/stores/auth');
      const store = useAuthStore();

      expect(store.token).toBe('persisted-token');
      expect(store.isAuthenticated).toBe(true);
    });
  });
});
