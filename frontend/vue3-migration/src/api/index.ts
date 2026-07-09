import type { AxiosError } from 'axios';
import axios, { type AxiosResponse, type InternalAxiosRequestConfig } from 'axios';
import { TOKEN_KEY } from '@/constants/storage-keys';
import TokenManager from '@/utils/TokenManager';
import { createLogger } from '@/utils/logger';

const logger = createLogger('api');

// ============================
// 类型扩展：给请求附加 _retry 标记
// ============================

declare module 'axios' {
  interface InternalAxiosRequestConfig {
    /** 是否已经重试过（防止无限重试） */
    _retry?: boolean;
  }
}

const MAX_RETRY = 1;

const apiClient = axios.create({
  // P2-6: baseURL 保持空字符串，利用 vite.config.ts 中的 proxy 进行 API 转发
  // 注意：生产环境部署时需要配置环境变量 VITE_API_BASE_URL，
  // 因为 vite proxy 仅在开发服务器中有效。建议用法：baseURL: import.meta.env.VITE_API_BASE_URL || '',
  baseURL: '',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ============================
// 请求拦截器 — 附加 Authorization 头
// ============================

apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = TokenManager.getToken();
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error: AxiosError) => {
    return Promise.reject(error);
  },
);

// ============================
// 响应拦截器 — 401 先刷新再重试
// ============================

apiClient.interceptors.response.use(
  (response: AxiosResponse) => response.data,
  async (error: AxiosError) => {
    const config = error.config as InternalAxiosRequestConfig | undefined;

    // 仅对 401 + 未重试过的请求尝试刷新
    if (error.response?.status === 401 && config && !config._retry) {
      config._retry = true;

      const newToken = await TokenManager.refreshToken();

      if (newToken) {
        // 刷新成功：用新 token 重试原请求
        logger.info('[API] Token 刷新成功，重试原请求');
        if (config.headers) {
          config.headers.Authorization = `Bearer ${newToken}`;
        }
        return apiClient.request(config);
      }

      // 刷新失败：清除 token 并跳转登录
      console.warn('[API] Token 刷新失败，跳转登录页');
      TokenManager.clearToken();

      import('@/router').then(({ default: router }) => {
        router.push('/login');
      });
    }

    return Promise.reject(error);
  },
);

export default apiClient;
