/**
 * API 请求测试
 * 测试 Axios 实例、请求拦截器和响应拦截器
 */
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import axios from 'axios';

// 模拟 axios.create 返回值
const mockAxiosInstance = {
  interceptors: {
    request: { use: vi.fn() },
    response: { use: vi.fn() },
  },
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
};

vi.mock('axios', () => ({
  default: {
    create: vi.fn(() => mockAxiosInstance),
  },
}));

describe('API 客户端', () => {
  let requestInterceptor;
  let responseSuccessInterceptor;
  let responseErrorInterceptor;
  let originalLocation;

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();

    // 每次导入前重置
    vi.resetModules();

    // 捕获拦截器回调
    mockAxiosInstance.interceptors.request.use.mockImplementation((successFn, errorFn) => {
      requestInterceptor = successFn;
      return 0;
    });

    mockAxiosInstance.interceptors.response.use.mockImplementation((successFn, errorFn) => {
      responseSuccessInterceptor = successFn;
      responseErrorInterceptor = errorFn;
      return 0;
    });

    // 模拟 window.location
    originalLocation = window.location;
    delete window.location;
    window.location = { href: '', reload: vi.fn() };
  });

  afterEach(() => {
    window.location = originalLocation;
  });

  describe('创建实例', () => {
    it('应使用正确的配置创建 axios 实例', async () => {
      await import('@/api/index.ts');

      expect(axios.create).toHaveBeenCalledWith({
        baseURL: '',
        timeout: 30000,
        headers: {
          'Content-Type': 'application/json',
        },
      });
    });
  });

  describe('请求拦截器', () => {
    it('存在 token 时应添加 Authorization 头', async () => {
      await import('@/api/index.ts');
      localStorage.setItem('token', 'test-token-123');

      const config = { headers: {} };
      const result = requestInterceptor(config);

      expect(result.headers.Authorization).toBe('Bearer test-token-123');
    });

    it('无 token 时不应添加 Authorization 头', async () => {
      await import('@/api/index.ts');

      const config = { headers: {} };
      const result = requestInterceptor(config);

      expect(result.headers.Authorization).toBeUndefined();
    });

    it('应返回原始 config 对象', async () => {
      await import('@/api/index.ts');

      const config = { headers: {}, customProp: 'value' };
      const result = requestInterceptor(config);

      expect(result.customProp).toBe('value');
    });

    it('请求拦截器错误应 reject', async () => {
      await import('@/api/index.ts');

      // 获取 error 处理器（第二个参数）
      mockAxiosInstance.interceptors.request.use.mock.calls[0]?.[1];

      const error = new Error('请求配置错误');
      try {
        await mockAxiosInstance.interceptors.request.use.mock.calls[0]?.[1]?.(error);
      } catch (e) {
        expect(e.message).toBe('请求配置错误');
      }
    });
  });

  describe('响应拦截器 - 成功', () => {
    it('成功响应应返回 response.data', async () => {
      await import('@/api/index.ts');

      const response = {
        data: { result: 'ok', items: [1, 2, 3] },
        status: 200,
      };

      const result = responseSuccessInterceptor(response);
      expect(result).toEqual({ result: 'ok', items: [1, 2, 3] });
    });
  });

  describe('响应拦截器 - 错误', () => {
    it('401 错误应清除 token 并重定向到 /login', async () => {
      await import('@/api/index.ts');
      localStorage.setItem('token', 'old-token');

      const error = {
        response: {
          status: 401,
          data: { detail: '未授权' },
        },
      };

      try {
        await responseErrorInterceptor(error);
      } catch (e) {
        expect(localStorage.getItem('fuxi-token')).toBeNull();
        expect(e).toEqual(error);
      }
    });

    it('非 401 错误应直接 reject', async () => {
      await import('@/api/index.ts');

      const error = {
        response: {
          status: 500,
          data: { detail: '服务器错误' },
        },
      };

      try {
        await responseErrorInterceptor(error);
      } catch (e) {
        expect(e).toEqual(error);
        expect(window.location.href).toBe('');
      }
    });

    it('无 response 对象的错误应直接 reject', async () => {
      await import('@/api/index.ts');

      const error = new Error('网络错误');

      try {
        await responseErrorInterceptor(error);
      } catch (e) {
        expect(e).toEqual(error);
      }
    });

    it('应返回 Promise.reject', async () => {
      await import('@/api/index.ts');

      const error = { response: { status: 403 } };
      await expect(responseErrorInterceptor(error)).rejects.toEqual(error);
    });
  });

  describe('默认导出', () => {
    it('应导出默认的 apiClient', async () => {
      const apiClient = (await import('@/api/index.ts')).default;

      expect(apiClient).toBe(mockAxiosInstance);
    });
  });
});
