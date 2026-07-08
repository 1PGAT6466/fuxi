/**
 * Login.vue 组件测试
 * 测试登录表单验证、交互和错误处理
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import Login from '@/views/Login.vue';
import { useAuthStore } from '@/stores/auth';

// Mock vue-router
vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
  useRoute: () => ({
    query: {},
  }),
}));

// Mock Element Plus icons
vi.mock('@element-plus/icons-vue', () => ({
  User: { name: 'User' },
  Lock: { name: 'Lock' },
  WarningFilled: { name: 'WarningFilled' },
}));

describe('Login.vue', () => {
  let wrapper;

  beforeEach(() => {
    setActivePinia(createPinia());
    // Use global.components instead of stubs because Vue 3 SFCs resolve
    // <el-button> etc. via resolveComponent which looks up globally registered
    // components (from app.use(ElementPlus)), not stubs.
    wrapper = mount(Login, {
      global: {
        components: {
          ElForm: {
            template: '<form @submit.prevent><slot /></form>',
            props: ['model', 'rules', 'ref'],
            methods: {
              validate() {
                const rules = this.$props.rules;
                const model = this.$props.model;
                const errors = [];

                if (!model.username || model.username.length < 2) {
                  errors.push({ field: 'username', message: '请输入用户名' });
                }
                if (!model.password || model.password.length < 6) {
                  errors.push({ field: 'password', message: '请输入密码' });
                }

                if (errors.length > 0) {
                  return Promise.reject(errors);
                }
                return Promise.resolve(true);
              },
            },
          },
          ElFormItem: {
            template: '<div class="el-form-item"><slot /></div>',
            props: ['prop'],
          },
          ElButton: {
            template: '<button class="el-button" :disabled="loading" @click="$emit(\'click\')"><slot /></button>',
            props: ['type', 'size', 'loading', 'nativeType'],
            emits: ['click'],
          },
          ElInput: {
            template: '<div class="el-input"><input class="el-input__inner" :value="modelValue" :placeholder="placeholder" :type="type" @input="$emit(\'update:modelValue\', $event.target.value)" @keyup.enter="$emit(\'keyup.enter\', $event)" /></div>',
            props: ['modelValue', 'placeholder', 'type', 'size', 'clearable', 'showPassword', 'prefixIcon'],
            emits: ['update:modelValue', 'keyup.enter'],
          },
          ElIcon: { template: '<i class="el-icon"><slot /></i>' },
        },
      },
    });
  });

  describe('组件渲染', () => {
    it('应该渲染登录表单', () => {
      expect(wrapper.find('.login-container').exists()).toBe(true);
      expect(wrapper.find('.login-card').exists()).toBe(true);
    });

    it('应该显示标题"伏羲·内世界"', () => {
      // $t mock returns last segment of key: login.title → 'title'
      expect(wrapper.text()).toContain('title');
    });

    it('应该显示副标题"企业知识认知系统"', () => {
      // $t mock returns last segment: login.subtitle → 'subtitle'
      expect(wrapper.text()).toContain('subtitle');
    });

    it('应该渲染用户名输入框', () => {
      const inputs = wrapper.findAll('input');
      expect(inputs.length).toBeGreaterThanOrEqual(1);
    });

    it('应该渲染登录按钮', () => {
      const btn = wrapper.find('.el-button');
      expect(btn.exists()).toBe(true);
      // $t('login.loginBtn') → 'loginBtn'
      expect(btn.text()).toBe('loginBtn');
    });
  });

  describe('表单验证', () => {
    it('用户名规则：必填', () => {
      const rules = wrapper.vm.rules;
      expect(rules.username[0].required).toBe(true);
      expect(rules.username[0].message).toBe('请输入用户名');
    });

    it('用户名规则：长度范围 2-50', () => {
      const rules = wrapper.vm.rules;
      expect(rules.username[1].min).toBe(2);
      expect(rules.username[1].max).toBe(50);
    });

    it('密码规则：必填', () => {
      const rules = wrapper.vm.rules;
      expect(rules.password[0].required).toBe(true);
      expect(rules.password[0].message).toBe('请输入密码');
    });

    it('密码规则：最小长度 6', () => {
      const rules = wrapper.vm.rules;
      expect(rules.password[1].min).toBe(6);
    });

    it('初始状态用户名应为空', () => {
      expect(wrapper.vm.form.username).toBe('');
    });

    it('初始状态密码应为空', () => {
      expect(wrapper.vm.form.password).toBe('');
    });

    it('初始状态 loading 应为 false', () => {
      expect(wrapper.vm.loading).toBe(false);
    });

    it('初始状态 error 应为空字符串', () => {
      expect(wrapper.vm.error).toBe('');
    });
  });

  describe('登录交互', () => {
    it('应设置用户名到 form 数据', async () => {
      wrapper.vm.form.username = 'admin';
      expect(wrapper.vm.form.username).toBe('admin');
    });

    it('应设置密码到 form 数据', async () => {
      wrapper.vm.form.password = 'password123';
      expect(wrapper.vm.form.password).toBe('password123');
    });

    it('formRef 未初始化时 handleLogin 应安全返回', async () => {
      wrapper.vm.formRef = null;
      // 应不抛出异常
      await expect(wrapper.vm.handleLogin()).resolves.toBeUndefined();
    });
  });
});
