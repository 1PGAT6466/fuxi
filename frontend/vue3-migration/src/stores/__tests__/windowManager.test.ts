/**
 * 伏羲 v2.1 — windowManager store 单元测试
 *
 * 覆盖：
 *  - 初始状态
 *  - open()：普通窗口 / singleton 窗口 / 全屏窗口
 *  - focus()：zIndex 递增 / 恢复最小化
 *  - minimize()：状态转换 / 活跃窗口切换
 *  - close()：closing → closed 状态转换 / 活跃窗口切换
 *  - move() / resize() 边界条件
 *  - 布局模式：tiled / split
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useWindowManager } from '@/stores/windowManager'
import type { ServiceManifest, ServiceWindow } from '@/types/service-manifest'

// ─── 工厂函数 ───

function createMockManifest(
  overrides: Partial<ServiceManifest> = {},
): ServiceManifest {
  return {
    id: 'test-service',
    name: 'Test Service',
    icon: '🧪',
    description: 'A test service',
    version: '1.0.0',
    category: 'workspace',
    route: '/test',
    apiBase: '/api/test',
    endpoints: [],
    requiredRole: 'user',
    windowMode: 'tab',
    ...overrides,
  }
}

describe('windowManager store', () => {
  let store: ReturnType<typeof useWindowManager>

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useWindowManager()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  // ══════════════════════════════════════════
  // 初始状态
  // ══════════════════════════════════════════

  describe('initial state', () => {
    it('windows 初始为空数组', () => {
      expect(store.windows).toEqual([])
    })

    it('activeWindowId 初始为 null', () => {
      expect(store.activeWindowId).toBeNull()
    })

    it('nextZIndex 初始为 100', () => {
      expect(store.nextZIndex).toBe(100)
    })

    it('layout.mode 初始为 free', () => {
      expect(store.layout.mode).toBe('free')
    })

    it('activeWindow 初始为 null', () => {
      expect(store.activeWindow).toBeNull()
    })

    it('visibleWindows 初始为空', () => {
      expect(store.visibleWindows).toEqual([])
    })

    it('closingWindowIds 初始为空 Set', () => {
      expect(store.closingWindowIds.size).toBe(0)
    })
  })

  // ══════════════════════════════════════════
  // open()
  // ══════════════════════════════════════════

  describe('open()', () => {
    it('open 返回一个 ServiceWindow 实例', () => {
      const manifest = createMockManifest()
      const win = store.open(manifest)

      expect(win.id).toBeDefined()
      expect(win.serviceId).toBe('test-service')
      expect(win.title).toBe('Test Service')
      expect(win.state).toBe('normal')
    })

    it('open 后将窗口加入 windows 数组', () => {
      const manifest = createMockManifest()
      const win = store.open(manifest)

      expect(store.windows.length).toBe(1)
      expect(store.windows[0].id).toBe(win.id)
    })

    it('open 后设置该窗口为活跃窗口', () => {
      store.open(createMockManifest())
      expect(store.activeWindowId).not.toBeNull()
      expect(store.activeWindow).toBeDefined()
    })

    it('open 窗口时 zIndex 递增', () => {
      store.open(createMockManifest())
      const firstZ = store.activeWindow!.zIndex

      store.open(createMockManifest({ id: 'another', name: 'Another' }))
      const secondZ = store.activeWindow!.zIndex

      expect(secondZ).toBeGreaterThan(firstZ)
    })

    it('fullscreen 模式的窗口初始状态为 maximized', () => {
      const manifest = createMockManifest({ id: 'full', windowMode: 'fullscreen' })
      const win = store.open(manifest)
      expect(win.state).toBe('maximized')
    })

    // ── singleton ──

    it('singleton 窗口重复 open 时不新增，而是聚焦已有窗口', () => {
      const singletonManifest = createMockManifest({
        id: 'singleton-svc',
        singleton: true,
      })

      const first = store.open(singletonManifest)
      // 先打开另一个窗口再切回来做对比
      store.open(createMockManifest({ id: 'other' }))

      // 再次 open 同一个 singleton
      const second = store.open(singletonManifest)

      expect(second.id).toBe(first.id)
      expect(store.windows.length).toBe(2) // 只有 singleton + other
    })

    it('singleton 窗口已 minimised 时重复 open 应恢复为 normal', () => {
      const manifest = createMockManifest({ id: 's', singleton: true })
      const win = store.open(manifest)
      store.minimize(win.id)
      expect(win.state).toBe('minimized')

      const reopened = store.open(manifest)
      expect(reopened.state).toBe('normal')
    })

    it('singleton 窗口 closed/closing 时重复 open 应新建', () => {
      const manifest = createMockManifest({ id: 's', singleton: true })
      const win = store.open(manifest)
      store.close(win.id)

      // 等 300ms 后窗口被删除
      vi.advanceTimersByTime(301)

      const newWin = store.open(manifest)
      expect(newWin.id).not.toBe(win.id)
      expect(store.windows.length).toBe(1)
    })

    it('open 支持传入 context 数据', () => {
      const manifest = createMockManifest()
      const win = store.open(manifest, { fileId: 'abc', page: 3 })
      expect(win.data).toEqual({ fileId: 'abc', page: 3 })
    })

    it('singleton 窗口重复 open 时合并 context', () => {
      const manifest = createMockManifest({ id: 's', singleton: true })
      store.open(manifest, { a: 1 })
      const win = store.open(manifest, { b: 2 })

      expect(win.data).toEqual({ a: 1, b: 2 })
    })
  })

  // ══════════════════════════════════════════
  // focus()
  // ══════════════════════════════════════════

  describe('focus()', () => {
    it('聚焦窗口时 zIndex 递增', () => {
      const w1 = store.open(createMockManifest({ id: 'a' }))
      store.open(createMockManifest({ id: 'b' }))

      const originalZ = w1.zIndex
      store.focus(w1.id)

      expect(w1.zIndex).toBeGreaterThan(originalZ)
      expect(store.activeWindowId).toBe(w1.id)
    })

    it('聚焦已 minimised 的窗口应恢复为 normal', () => {
      const win = store.open(createMockManifest())
      store.minimize(win.id)
      expect(win.state).toBe('minimized')

      store.focus(win.id)
      expect(win.state).toBe('normal')
    })

    it('聚焦不存在的 ID 无异常', () => {
      expect(() => store.focus('nonexistent')).not.toThrow()
    })
  })

  // ══════════════════════════════════════════
  // minimize()
  // ══════════════════════════════════════════

  describe('minimize()', () => {
    it('窗口状态从 normal 变为 minimized', () => {
      const win = store.open(createMockManifest())
      store.minimize(win.id)

      expect(win.state).toBe('minimized')
    })

    it('minimise 不存在的窗口不报错', () => {
      expect(() => store.minimize('noop')).not.toThrow()
    })

    it('minimise 活跃窗口后切换到下一个可见窗口', () => {
      const w1 = store.open(createMockManifest({ id: 'a' }))
      const w2 = store.open(createMockManifest({ id: 'b' }))

      // w2 是活跃窗口
      store.minimize(w2.id)

      expect(store.activeWindowId).toBe(w1.id)
    })

    it('minimise 最后一个窗口后 activeWindowId 为 null', () => {
      const win = store.open(createMockManifest())
      store.minimize(win.id)

      expect(store.activeWindowId).toBeNull()
    })
  })

  // ══════════════════════════════════════════
  // toggleMaximize()
  // ══════════════════════════════════════════

  describe('toggleMaximize()', () => {
    it('normal → maximized', () => {
      const win = store.open(createMockManifest())
      store.toggleMaximize(win.id)
      expect(win.state).toBe('maximized')
    })

    it('maximized → normal', () => {
      const win = store.open(createMockManifest())
      store.toggleMaximize(win.id) // → maximized
      store.toggleMaximize(win.id) // → normal
      expect(win.state).toBe('normal')
    })

    it('对 minimised 窗口无效', () => {
      const win = store.open(createMockManifest())
      store.minimize(win.id)
      store.toggleMaximize(win.id)
      expect(win.state).toBe('minimized')
    })
  })

  // ══════════════════════════════════════════
  // close()
  // ══════════════════════════════════════════

  describe('close()', () => {
    it('关闭窗口时状态变为 closing', () => {
      const win = store.open(createMockManifest())
      store.close(win.id)

      expect(win.state).toBe('closing')
    })

    it('关闭时将 window id 加入 closingWindowIds', () => {
      const win = store.open(createMockManifest())
      store.close(win.id)

      expect(store.closingWindowIds.has(win.id)).toBe(true)
    })

    it('300ms 后窗口从 windows 数组中移除', () => {
      const win = store.open(createMockManifest())
      store.close(win.id)

      // 100ms 时还在 closingWindowIds
      vi.advanceTimersByTime(100)
      expect(store.closingWindowIds.has(win.id)).toBe(true)

      // 300ms 后彻底移除
      vi.advanceTimersByTime(301)
      expect(store.windows.find((w) => w.id === win.id)).toBeUndefined()
      expect(store.closingWindowIds.has(win.id)).toBe(false)
    })

    it('关闭活跃窗口后切换到下一个', () => {
      const w1 = store.open(createMockManifest({ id: 'a' }))
      const w2 = store.open(createMockManifest({ id: 'b' }))

      store.close(w2.id)

      vi.advanceTimersByTime(301)
      expect(store.activeWindowId).toBe(w1.id)
    })

    it('关闭最后窗口后 activeWindowId 为 null', () => {
      const win = store.open(createMockManifest())
      store.close(win.id)

      vi.advanceTimersByTime(301)
      expect(store.activeWindowId).toBeNull()
      expect(store.windows.length).toBe(0)
    })

    it('重复 close 同一窗口无副作用', () => {
      const win = store.open(createMockManifest())
      store.close(win.id)
      store.close(win.id) // 第二次不应报错

      vi.advanceTimersByTime(301)
      expect(store.windows.length).toBe(0)
    })
  })

  // ══════════════════════════════════════════
  // move() & resize()
  // ══════════════════════════════════════════

  describe('move()', () => {
    it('更新窗口位置', () => {
      const win = store.open(createMockManifest())
      store.move(win.id, 200, 150)

      expect(win.position).toEqual({ x: 200, y: 150 })
    })

    it('移动不存在的窗口不报错', () => {
      expect(() => store.move('nonexistent', 0, 0)).not.toThrow()
    })
  })

  describe('resize()', () => {
    it('更新窗口尺寸', () => {
      const win = store.open(createMockManifest())
      store.resize(win.id, 1024, 768)

      expect(win.size.width).toBe(1024)
      expect(win.size.height).toBe(768)
    })

    it('尺寸不能小于最小值 320x240', () => {
      const win = store.open(createMockManifest())
      store.resize(win.id, 100, 50)

      expect(win.size.width).toBe(320)
      expect(win.size.height).toBe(240)
    })

    it('maximised 窗口不能 resize', () => {
      const win = store.open(createMockManifest())
      store.toggleMaximize(win.id)
      const originalSize = { ...win.size }

      store.resize(win.id, 2000, 2000)

      expect(win.size).toEqual(originalSize)
    })
  })

  // ══════════════════════════════════════════
  // 布局
  // ══════════════════════════════════════════

  describe('setLayout()', () => {
    it('切换到 tiled 布局', () => {
      store.open(createMockManifest({ id: 'a' }))
      store.open(createMockManifest({ id: 'b' }))

      expect(() => store.setLayout('tiled')).not.toThrow()
      expect(store.layout.mode).toBe('tiled')
    })

    it('切换到 split 布局', () => {
      store.open(createMockManifest({ id: 'a' }))
      store.open(createMockManifest({ id: 'b' }))

      expect(() => store.setLayout('split', { ratios: [0.6, 0.4] })).not.toThrow()
      expect(store.layout.mode).toBe('split')
    })

    it('无 normal 窗口时切换布局不报错', () => {
      expect(() => store.setLayout('tiled')).not.toThrow()
    })
  })

  // ══════════════════════════════════════════
  // Getter: visibleWindows
  // ══════════════════════════════════════════

  describe('visibleWindows', () => {
    it('排除 closed 和 closing 状态的窗口', () => {
      store.open(createMockManifest({ id: 'a' }))
      const b = store.open(createMockManifest({ id: 'b' }))
      store.close(b.id)

      // b 是 closing 状态，不应该在 visibleWindows 中
      const visible = store.visibleWindows
      expect(visible.length).toBe(1)
      expect(visible[0].serviceId).toBe('a')
    })

    it('minimised 窗口仍在 visibleWindows 中', () => {
      const win = store.open(createMockManifest())
      store.minimize(win.id)

      expect(store.visibleWindows.length).toBe(1)
      expect(store.visibleWindows[0].state).toBe('minimized')
    })
  })

  // ══════════════════════════════════════════
  // Getter: windowsByService
  // ══════════════════════════════════════════

  describe('windowsByService', () => {
    it('按 serviceId 正确分组', () => {
      store.open(createMockManifest({ id: 'svc-a' }))
      store.open(createMockManifest({ id: 'svc-a' }))
      store.open(createMockManifest({ id: 'svc-b' }))

      const byService = store.windowsByService
      expect(byService['svc-a'].length).toBe(2)
      expect(byService['svc-b'].length).toBe(1)
    })
  })
})
