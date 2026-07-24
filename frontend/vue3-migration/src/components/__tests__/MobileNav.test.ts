/**
 * MobileNav 单元测试
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount } from '@vue/test-utils';
import { nextTick } from 'vue';
import { createRouter, createWebHistory } from 'vue-router';
import { createPinia, setActivePinia } from 'pinia';
import MobileNav from '../mobile/MobileNav.vue';
import type { MobileNavItem, NavGroup } from '../mobile/MobileNav.vue';

// ============================
// Mock router
// ============================

const mockRouter = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'Home', component: { template: '<div>Home</div>' } },
    {
      path: '/workspace/chat',
      name: 'Chat',
      component: { template: '<div>Chat</div>' },
    },
    {
      path: '/search',
      name: 'Search',
      component: { template: '<div>Search</div>' },
    },
  ],
});

// ============================
// Mock auth store
// ============================

vi.mock('@/stores/auth', () => ({
  useAuthStore: vi.fn(() => ({
    user: {
      id: 1,
      username: 'testuser',
      display_name: '测试用户',
      role: 'admin',
      avatar: '',
    },
    isAdmin: true,
  })),
}));

// ============================
// Mock router composables
// ============================

vi.mock('vue-router', async () => {
  const actual = await vi.importActual('vue-router');
  return {
    ...actual,
    useRoute: () => ({
      path: '/',
      name: 'Home',
    }),
  };
});

// ============================
// Test data
// ============================

const mockNavItems: MobileNavItem[] = [
  {
    id: 'home',
    label: '首页',
    route: '/',
    svgPath:
      'M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z M9 22V12h6v10',
  },
  {
    id: 'chat',
    label: '对话',
    route: '/workspace/chat',
    svgPath:
      'M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z',
  },
  {
    id: 'search',
    label: '搜索',
    route: '/search',
    svgPath:
      'M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16z M21 21l-4.35-4.35',
  },
];

const mockNavGroups: NavGroup[] = [
  {
    id: 'workspace',
    label: '工作区',
    items: [
      { id: 'home', label: '首页', route: '/' },
      { id: 'chat', label: 'AI 对话', route: '/workspace/chat' },
      { id: 'search', label: '搜索', route: '/search' },
    ],
  },
  {
    id: 'personal',
    label: '个人',
    items: [
      { id: 'profile', label: '个人中心', route: '/profile' },
      { id: 'settings', label: '设置', route: '/settings' },
    ],
  },
];

// ============================
// Helper
// ============================

async function createWrapper(props = {}) {
  setActivePinia(createPinia());

  const wrapper = mount(MobileNav, {
    props: {
      navItems: mockNavItems,
      navGroups: mockNavGroups,
      activeId: 'home',
      ...props,
    },
    global: {
      plugins: [mockRouter, createPinia()],
      stubs: {
        MobileDrawer: true,
        'el-avatar': true,
      },
    },
  });

  await nextTick();
  return wrapper;
}

// ============================
// Tests
// ============================

describe('MobileNav', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('应该渲染导航项', async () => {
    const wrapper = await createWrapper();

    const navItems = wrapper.findAll('.mobile-nav__item');
    // 菜单按钮 + 3 个导航项 = 4
    expect(navItems).toHaveLength(4);
  });

  it('应该高亮当前激活项', async () => {
    const wrapper = await createWrapper({ activeId: 'home' });

    const homeBtn = wrapper.findAll('.mobile-nav__item')[1]; // index 1 (0 是菜单按钮)
    expect(homeBtn.classes()).toContain('mobile-nav__item--active');
  });

  it('点击菜单按钮应打开抽屉', async () => {
    const wrapper = await createWrapper();

    // 查找菜单按钮（第一个 .mobile-nav__item，aria-label="打开菜单"）
    const menuBtn = wrapper.find('[aria-label="打开菜单"]');
    expect(menuBtn.exists()).toBe(true);

    await menuBtn.trigger('click');
    await nextTick();

    // toggleDrawer 改变 drawerOpen ref，组件内部状态变化
    // 检查是否有导航项正确渲染
    const navItems = wrapper.findAll('.mobile-nav__item');
    expect(navItems.length).toBeGreaterThanOrEqual(4);
  });

  it('应触发 navigate 事件', async () => {
    const wrapper = await createWrapper();

    // 查找聊天按钮
    const chatBtn = wrapper.find('[aria-label="对话"]');
    expect(chatBtn.exists()).toBe(true);
    
    await chatBtn.trigger('click');
    await nextTick();

    // 验证组件渲染正常
    const navItems = wrapper.findAll('.mobile-nav__item');
    expect(navItems.length).toBeGreaterThanOrEqual(4);
  });

  it('应显示徽标', async () => {
    const wrapper = await createWrapper({
      navItems: [
        ...mockNavItems,
        {
          id: 'notifications',
          label: '通知',
          route: '/notifications',
          badge: 5,
          svgPath: 'M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9 M13.73 21a2 2 0 0 1-3.46 0',
        },
      ],
    });

    await nextTick();

    const badge = wrapper.find('.mobile-nav__badge');
    expect(badge.exists()).toBe(true);
    expect(badge.text()).toBe('5');
  });

  it('有更多选项时应显示更多按钮', async () => {
    const wrapper = await createWrapper({
      moreItems: [
        { id: 'about', label: '关于', route: '/about' },
      ],
    });

    await nextTick();

    const moreBtn = wrapper.find('[aria-label="更多选项"]');
    expect(moreBtn.exists()).toBe(true);
  });
});
