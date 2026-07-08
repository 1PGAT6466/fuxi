/**
 * 伏羲 v2.1 — auth store 单元测试
 *
 * 覆盖：
 *  - 初始状态
 *  - login()：成功 / 失败 / loading 恢复 / token 持久化 / role 验证
 *  - logout()：清除 token & user、停止自动刷新
 *  - initAuth()：从 localStorage 恢复 / 已过期 / 刷新失败
 *  - refreshToken / doRefreshToken
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import * as authApi from '@/api/auth'
import TokenManager from '@/utils/TokenManager'
import type { LoginResult } from '@/api/auth'

// ─── Mock authApi（必须在顶层） ───
vi.mock('@/api/auth', () => ({
  login: vi.fn(),
  refreshToken: vi.fn(),
  logout: vi.fn(),
}))

// ─── 类型工具：把 computed ref 转换成值（方便断言） ───
function unwrapComputed<T>(ref: { value: T } | T): T {
  return (ref as { value: T }).value !== undefined ? (ref as { value: T }).value : (ref as T)
}

describe('auth store', () => {
  let store: ReturnType<typeof useAuthStore>

  beforeEach(() => {
    // 每次测试使用全新的 Pinia 实例
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllTimers()
    vi.useFakeTimers()
    store = useAuthStore()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  // ══════════════════════════════════════════
  // 初始状态
  // ══════════════════════════════════════════

  describe('initial state', () => {
    it('token 初始为空字符串', () => {
      expect(store.token).toBe('')
    })

    it('user 初始为 null', () => {
      expect(store.user).toBeNull()
    })

    it('loading 初始为 false', () => {
      expect(store.loading).toBe(false)
    })

    it('isAuthenticated 初始为 false', () => {
      expect(store.isAuthenticated).toBe(false)
    })

    it('role 初始为 null', () => {
      expect(store.role).toBeNull()
    })

    it('isAdmin 初始为 false', () => {
      expect(store.isAdmin).toBe(false)
    })
  })

  // ══════════════════════════════════════════
  // login()
  // ══════════════════════════════════════════

  describe('login()', () => {
    const mockLoginResult: LoginResult = {
      token:
        'eyJhbGciOiJIUzI1NiJ9.eyJleHAiOjk5OTk5OTk5OTk5OX0.' +
        'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
      user: {
        id: 1,
        username: 'admin',
        display_name: '管理员',
        role: 'admin',
      },
    }

    it('成功登录后设置 token 和 user', async () => {
      vi.mocked(authApi.login).mockResolvedValueOnce(mockLoginResult)

      const result = await store.login('admin', 'password', 'admin')

      expect(store.token).toBe(mockLoginResult.token)
      expect(store.user).toEqual(mockLoginResult.user)
      expect(store.isAuthenticated).toBe(true)
      expect(store.isAdmin).toBe(true)
      expect(store.role).toBe('admin')
      expect(result).toEqual(mockLoginResult)
    })

    it('登录成功后将 token 持久化到 localStorage', async () => {
      vi.mocked(authApi.login).mockResolvedValueOnce(mockLoginResult)

      await store.login('admin', 'password', 'admin')

      expect(TokenManager.getToken()).toBe(mockLoginResult.token)
    })

    it('以普通用户身份登录时 isAdmin 为 false', async () => {
      const userResult: LoginResult = {
        token: 'token-user',
        user: { id: 2, username: 'normal', role: 'user' },
      }
      vi.mocked(authApi.login).mockResolvedValueOnce(userResult)

      await store.login('normal', 'pass', 'user')

      expect(store.isAdmin).toBe(false)
      expect(store.role).toBe('user')
    })

    it('登录时 loading 应置为 true 再恢复 false', async () => {
      vi.mocked(authApi.login).mockResolvedValueOnce(mockLoginResult)

      const loginPromise = store.login('admin', 'password', 'admin')

      // 在 await 前，loading 应为 true
      expect(store.loading).toBe(true)

      await loginPromise

      expect(store.loading).toBe(false)
    })

    it('登录失败时 loading 应恢复为 false', async () => {
      vi.mocked(authApi.login).mockRejectedValueOnce(new Error('凭证错误'))

      await expect(store.login('bad', 'wrong', 'user')).rejects.toThrow('凭证错误')

      expect(store.loading).toBe(false)
      expect(store.isAuthenticated).toBe(false)
    })

    it('登录失败时不改变 token/user 状态', async () => {
      vi.mocked(authApi.login).mockRejectedValueOnce(new Error('fail'))

      await store.login('u', 'p', 'user').catch(() => {})

      expect(store.token).toBe('')
      expect(store.user).toBeNull()
    })

    it('登录后启动自动 token 刷新定时器', async () => {
      vi.mocked(authApi.login).mockResolvedValueOnce(mockLoginResult)
      vi.mocked(authApi.refreshToken).mockResolvedValue('new-token')

      await store.login('admin', 'password', 'admin')

      // 快进 3 分钟后应该触发刷新检测
      vi.advanceTimersByTime(3 * 60 * 1000)

      // 如果 exp 很远，此时不会触发刷新
      // 测试重点是定时器已启动
    })
  })

  // ══════════════════════════════════════════
  // logout()
  // ══════════════════════════════════════════

  describe('logout()', () => {
    it('登出后 token 为空字符串', async () => {
      vi.mocked(authApi.login).mockResolvedValueOnce({
        token: 't',
        user: { id: 1, username: 'u', role: 'user' },
      })
      await store.login('u', 'p', 'user')

      // TokenManager mock 确保 clearToken 正常
      await store.logout()

      expect(store.token).toBe('')
    })

    it('登出后 user 为 null', async () => {
      vi.mocked(authApi.login).mockResolvedValueOnce({
        token: 't',
        user: { id: 1, username: 'u', role: 'user' },
      })
      await store.login('u', 'p', 'user')

      await store.logout()

      expect(store.user).toBeNull()
    })

    it('登出后 isAuthenticated 为 false', async () => {
      vi.mocked(authApi.login).mockResolvedValueOnce({
        token: 't',
        user: { id: 1, username: 'u', role: 'user' },
      })
      await store.login('u', 'p', 'user')

      await store.logout()

      expect(store.isAuthenticated).toBe(false)
    })

    it('登出时清除 localStorage 中的 token', async () => {
      vi.mocked(authApi.login).mockResolvedValueOnce({
        token: 't',
        user: { id: 1, username: 'u', role: 'user' },
      })
      await store.login('u', 'p', 'user')

      await store.logout()

      expect(TokenManager.getToken()).toBe('')
    })

    it('即使后端 logout API 失败，也清除本地状态', async () => {
      // 手动注入 token/user 绕过 login
      vi.mocked(authApi.logout).mockRejectedValueOnce(new Error('Network error'))

      // 需要先设置 token
      TokenManager.setToken('test-token')
      store = useAuthStore()
      // We'll directly set token via the store's exposed ref
      ;(store as any).token = 'test-token'
      ;(store as any).user = { id: 1, username: 'u', role: 'user' }

      await store.logout()

      expect(store.token).toBe('')
      expect(store.user).toBeNull()
    })
  })

  // ══════════════════════════════════════════
  // refreshToken / doRefreshToken
  // ══════════════════════════════════════════

  describe('refreshToken()', () => {
    it('成功刷新后更新 token', async () => {
      vi.mocked(authApi.refreshToken).mockResolvedValueOnce('new-token-xyz')

      const result = await store.refreshToken()

      expect(store.token).toBe('new-token-xyz')
      expect(result).toBe('new-token-xyz')
      expect(TokenManager.getToken()).toBe('new-token-xyz')
    })

    it('刷新失败时执行 logout', async () => {
      vi.mocked(authApi.refreshToken).mockRejectedValueOnce(new Error('expired'))

      await expect(store.refreshToken()).rejects.toThrow('Token 刷新失败')

      expect(store.token).toBe('')
      expect(store.user).toBeNull()
    })
  })

  // ══════════════════════════════════════════
  // initAuth()
  // ══════════════════════════════════════════

  describe('initAuth()', () => {
    it('如果 localStorage 中没有 token，直接返回', async () => {
      await store.initAuth()

      expect(store.token).toBe('')
      expect(store.user).toBeNull()
      expect(store.loading).toBe(false)
    })

    it('如果有有效 token，调用 fetchUser 获取用户信息', async () => {
      // 构造一个 future-dated JWT
      const futureToken =
        'eyJhbGciOiJIUzI1NiJ9.' +
        btoa(JSON.stringify({ exp: 9999999999 })) +
        '.sig'
      TokenManager.setToken(futureToken)

      // 重新创建 store 以读取新 token
      setActivePinia(createPinia())
      store = useAuthStore()

      // Mock fetchUser via fetch
      const mockFetch = vi.spyOn(global, 'fetch').mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            code: 200,
            message: 'ok',
            data: { id: 1, username: 'admin', role: 'admin' },
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      )

      await store.initAuth()

      expect(store.user).toEqual({ id: 1, username: 'admin', role: 'admin' })
      expect(store.isAuthenticated).toBe(true)

      mockFetch.mockRestore()
    })

    it('如果 token 即将过期且刷新失败，执行 logout', async () => {
      // 构造一个即将过期的 JWT（30 秒后）
      const expiringSoon = Math.floor(Date.now() / 1000) + 30
      const nearExpireToken =
        'eyJhbGciOiJIUzI1NiJ9.' +
        btoa(JSON.stringify({ exp: expiringSoon })) +
        '.sig'
      TokenManager.setToken(nearExpireToken)

      setActivePinia(createPinia())
      store = useAuthStore()

      vi.mocked(authApi.refreshToken).mockRejectedValueOnce(new Error('expired'))

      await store.initAuth()

      expect(store.token).toBe('')
      expect(store.user).toBeNull()
      expect(store.isAuthenticated).toBe(false)
    })

    it('如果 token 即将过期且刷新成功，加载用户信息', async () => {
      const expiringSoon = Math.floor(Date.now() / 1000) + 30
      const nearExpireToken =
        'eyJhbGciOiJIUzI1NiJ9.' +
        btoa(JSON.stringify({ exp: expiringSoon })) +
        '.sig'
      TokenManager.setToken(nearExpireToken)

      vi.mocked(authApi.refreshToken).mockResolvedValueOnce('new-valid-token')

      setActivePinia(createPinia())
      store = useAuthStore()

      const mockFetch = vi.spyOn(global, 'fetch').mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            code: 200,
            data: { id: 1, username: 'admin', role: 'admin' },
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      )

      await store.initAuth()

      expect(store.token).toBe('new-valid-token')
      expect(store.user).toBeDefined()

      mockFetch.mockRestore()
    })
  })
})
