/**
 * Search.vue 组件测试
 * 测试搜索功能、防抖和结果展示
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';

// Mock API client
vi.mock('@/api', () => ({
  default: {
    get: vi.fn(),
  },
}));

// Mock Element Plus icons
vi.mock('@element-plus/icons-vue', () => ({
  Search: { name: 'Search' },
}));

// Mock sub-component
vi.mock('@/components/search/SearchResult.vue', () => ({
  default: {
    name: 'SearchResult',
    props: ['result'],
    template: '<div class="search-result">{{ result.title }}</div>',
  },
}));

describe('Search.vue', () => {
  let wrapper;
  let apiClient;

  beforeEach(async () => {
    setActivePinia(createPinia());

    apiClient = (await import('@/api')).default;

    const Search = (await import('@/views/Search.vue')).default;
    // Use global.components instead of stubs because Vue 3 SFCs resolve
    // <el-input> etc. via resolveComponent which looks up globally registered
    // components (from app.use(ElementPlus)), not stubs.
    wrapper = mount(Search, {
      global: {
        components: {
          ElInput: {
            template: '<div class="el-input"><input class="el-input__inner" :value="modelValue" :placeholder="placeholder" @input="$emit(\'update:modelValue\', $event.target.value)" @keyup.enter="$emit(\'keyup.enter\')" /><div class="el-input-group__append"><slot name="append" /></div></div>',
            props: ['modelValue', 'placeholder', 'size', 'clearable'],
            emits: ['update:modelValue', 'keyup.enter'],
          },
          ElButton: {
            template: '<button class="el-button" :disabled="loading" @click="$emit(\'click\')"><slot /></button>',
            props: ['loading', 'type', 'size'],
            emits: ['click'],
          },
          ElIcon: { template: '<i class="el-icon"><slot /></i>' },
          ElEmpty: { template: '<div class="el-empty"><slot /></div>', props: ['description'] },
        },
        stubs: {
          SearchResult: true,
        },
      },
    });
  });

  describe('组件渲染', () => {
    it('应该渲染搜索容器', () => {
      expect(wrapper.find('.search-container').exists()).toBe(true);
    });

    it('应该渲染搜索输入框', () => {
      expect(wrapper.find('.el-input').exists()).toBe(true);
    });

    it('应该渲染搜索按钮', () => {
      expect(wrapper.find('.el-button').exists()).toBe(true);
    });
  });

  describe('搜索状态初始化', () => {
    it('初始查询字符串为空', () => {
      expect(wrapper.vm.query).toBe('');
    });

    it('初始结果列表为空', () => {
      expect(wrapper.vm.results).toEqual([]);
    });

    it('初始 loading 为 false', () => {
      expect(wrapper.vm.loading).toBe(false);
    });

    it('初始 searched 为 false', () => {
      expect(wrapper.vm.searched).toBe(false);
    });
  });

  describe('搜索输入', () => {
    it('应更新查询字符串', async () => {
      wrapper.vm.query = '人工智能';
      expect(wrapper.vm.query).toBe('人工智能');
    });

    it('空输入时不应搜索', async () => {
      wrapper.vm.query = '   ';
      await wrapper.vm.handleSearch();
      expect(apiClient.get).not.toHaveBeenCalled();
    });
  });

  describe('搜索结果', () => {
    it('成功响应时应设置结果', async () => {
      const mockResults = [
        { id: 1, title: 'AI概述', content: '...' },
        { id: 2, title: '机器学习', content: '...' },
      ];

      apiClient.get.mockResolvedValueOnce({ results: mockResults });

      wrapper.vm.query = 'AI';
      await wrapper.vm.handleSearch();

      expect(apiClient.get).toHaveBeenCalledWith('/api/search', {
        params: { q: 'AI', top_k: 10 },
      });
      expect(wrapper.vm.results).toEqual(mockResults);
    });

    it('响应无结果时应设为空数组', async () => {
      apiClient.get.mockResolvedValueOnce({});

      wrapper.vm.query = '不存在的关键词';
      await wrapper.vm.handleSearch();

      expect(wrapper.vm.results).toEqual([]);
    });

    it('API 错误时应设为空数组', async () => {
      apiClient.get.mockRejectedValueOnce(new Error('网络错误'));

      wrapper.vm.query = '测试';
      await wrapper.vm.handleSearch();

      expect(wrapper.vm.results).toEqual([]);
    });

    it('搜索后 loading 应恢复为 false', async () => {
      apiClient.get.mockResolvedValueOnce({ results: [] });

      wrapper.vm.query = 'test';
      await wrapper.vm.handleSearch();

      expect(wrapper.vm.loading).toBe(false);
    });
  });

  describe('清空搜索', () => {
    it('查询清空时应重置结果和 searched', async () => {
      // 先设置结果和已搜索状态
      wrapper.vm.results = [{ id: 1 }];
      wrapper.vm.searched = true;

      // 方式 A：通过 input 事件触发 v-model 的 update:modelValue，
      // 这会正确触发 watch(query) 回调
      const input = wrapper.find('.el-input__inner');
      // 先输入内容再清空，确保 watcher 检测到值变更
      await input.setValue('something');
      await input.setValue('');

      expect(wrapper.vm.results).toEqual([]);
      expect(wrapper.vm.searched).toBe(false);
    });
  });

  describe('searched 状态', () => {
    it('执行搜索后 searched 应为 true', async () => {
      apiClient.get.mockResolvedValueOnce({ results: [] });

      wrapper.vm.query = 'valid';
      await wrapper.vm.handleSearch();

      expect(wrapper.vm.searched).toBe(true);
    });
  });
});
