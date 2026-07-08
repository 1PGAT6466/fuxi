/**
 * Vitest 全局 Setup 文件
 * 在每次测试运行前执行
 */

import { config } from '@vue/test-utils';

// 提供一个全局的 $t 函数作为 i18n 的简单替代
// 这避免了在测试环境中导入 vue-i18n 的 ESM 模块问题
const mockT = (key: string): string => {
  // 返回翻译 key 的最后一段作为显示文本
  const parts = key.split('.');
  return parts[parts.length - 1] || key;
};

// 注入全局 i18n mock - 直接在 globalProperties 上提供 $t
config.global.mocks = {
  $t: mockT,
};

// 模拟 Element Plus 组件的全局属性
config.global.stubs = {
  'el-button': { template: '<button class="el-button" :disabled="disabled"><slot /></button>', props: ['type', 'size', 'loading', 'disabled', 'nativeType'] },
  'el-input': {
    template: `
      <div class="el-input">
        <input
          :value="modelValue"
          :placeholder="placeholder"
          :type="type"
          @input="$emit('update:modelValue', $event.target.value)"
          @keyup.enter="$emit('keyup.enter', $event)"
          class="el-input__inner"
        />
      </div>
    `,
    props: ['modelValue', 'placeholder', 'type', 'size', 'clearable', 'showPassword'],
    emits: ['update:modelValue', 'keyup.enter'],
  },
  'el-form': { template: '<form @submit.prevent><slot /></form>', props: ['model', 'rules', 'ref'] },
  'el-form-item': { template: '<div class="el-form-item"><slot /></div>', props: ['prop'] },
  'el-icon': { template: '<i class="el-icon"><slot /></i>' },
  'el-tag': { template: '<span class="el-tag" :type="type"><slot /></span>', props: ['type'] },
  'el-empty': { template: '<div class="el-empty"><slot /></div>', props: ['description'] },
  'el-avatar': { template: '<div class="el-avatar" :size="size"><slot /></div>', props: ['size'] },
  'el-table': { template: '<table class="el-table"><slot /></table>', props: ['data', 'vLoading'] },
  'el-table-column': {
    template: '<th class="el-table-column"><slot /></th>',
    props: ['prop', 'label', 'minWidth', 'width', 'fixed'],
  },
  'el-dialog': { template: '<div v-if="modelValue" class="el-dialog"><slot /></div>', props: ['modelValue', 'title', 'width'] },
  'el-message': { template: '<div class="el-message"><slot /></div>' },
  'el-message-box': { template: '<div class="el-message-box"><slot /></div>' },
  transition: false,
};

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => { store[key] = value; },
    removeItem: (key: string) => { delete store[key]; },
    clear: () => { store = {}; },
    get length() { return Object.keys(store).length; },
    key: (index: number) => Object.keys(store)[index] || null,
  };
})();

Object.defineProperty(global, 'localStorage', {
  value: localStorageMock,
  writable: true,
});

// Mock matchMedia (for Element Plus responsive)
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});
