<template>
  <!--
    伏羲 v2.1 — 登录页面（重构版）
    小米简约风 · 双角色Tab · 背景太极旋转动画 · 登录失败输入框抖动
    参考飞书登录风格，保留 auth store 逻辑不变
  -->
  <div class="login-page" :class="{ 'login-page--success': loginSuccess }">
    <!-- 背景太极 SVG 旋转动画 -->
    <div class="login-bg-tajii">
      <svg
        class="login-tajii-svg"
        viewBox="0 0 200 200"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <defs>
          <radialGradient id="tajii-grad" cx="50%" cy="50%">
            <stop offset="0%" stop-color="var(--fuxi-primary)" stop-opacity="0.15" />
            <stop offset="100%" stop-color="var(--fuxi-primary)" stop-opacity="0.02" />
          </radialGradient>
        </defs>
        <circle cx="100" cy="100" r="98" fill="none" stroke="var(--fuxi-primary)" stroke-width="1" opacity="0.3" />
        <!-- 太极阴阳鱼 -->
        <path
          d="M100,2 A98,98 0 0,1 100,198 A49,49 0 0,1 100,100 A49,49 0 0,0 100,2 Z"
          fill="var(--fuxi-primary)"
          opacity="0.2"
        />
        <path
          d="M100,2 A98,98 0 0,0 100,198 A49,49 0 0,0 100,100 A49,49 0 0,1 100,2 Z"
          fill="transparent"
          stroke="var(--fuxi-primary)"
          stroke-width="0.5"
          opacity="0.15"
        />
        <!-- 小圆点 -->
        <circle cx="100" cy="51" r="12" fill="var(--fuxi-primary)" opacity="0.18" />
        <circle cx="100" cy="51" r="5" fill="var(--fuxi-bg-card)" opacity="0.6" />
        <circle cx="100" cy="149" r="12" fill="var(--fuxi-bg-card)" opacity="0.3" />
        <circle cx="100" cy="149" r="5" fill="var(--fuxi-primary)" opacity="0.25" />

        <!-- 外圈八卦符号 -->
        <g font-size="14" font-family="serif" fill="var(--fuxi-primary)" opacity="0.5" text-anchor="middle">
          <text x="100" y="16" dx="1">☰</text>
          <text x="168" y="38">☱</text>
          <text x="186" y="106">☲</text>
          <text x="168" y="172">☳</text>
          <text x="100" y="194" dx="1">☴</text>
          <text x="32"  y="172">☵</text>
          <text x="14"  y="106">☶</text>
          <text x="32"  y="38">☷</text>
        </g>
      </svg>
    </div>

    <!-- 登录卡片 -->
    <div
      class="login-card"
      :class="{
        'login-card--shake': shakeCard,
        'login-card--fadeout': loginSuccess,
      }"
    >
      <!-- 品牌标识 -->
      <div class="login-brand">
        <div class="login-brand-icon-wrapper">
          <svg class="login-brand-tajii" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
            <circle cx="24" cy="24" r="23" fill="none" :stroke="'var(--fuxi-primary)'" stroke-width="1.5" opacity="0.4" />
            <path
              d="M24,1 A23,23 0 0,1 24,47 A11.5,11.5 0 0,1 24,24 A11.5,11.5 0 0,0 24,1 Z"
              fill="var(--fuxi-primary)"
              opacity="0.7"
            />
            <path
              d="M24,1 A23,23 0 0,0 24,47 A11.5,11.5 0 0,0 24,24 A11.5,11.5 0 0,1 24,1 Z"
              fill="var(--fuxi-bg-card)"
              opacity="0.8"
            />
            <circle cx="24" cy="12.5" r="4" fill="var(--fuxi-primary)" opacity="0.6" />
            <circle cx="24" cy="12.5" r="1.8" fill="var(--fuxi-bg-card)" />
            <circle cx="24" cy="35.5" r="4" fill="var(--fuxi-bg-card)" opacity="0.7" />
            <circle cx="24" cy="35.5" r="1.8" fill="var(--fuxi-primary)" opacity="0.6" />
          </svg>
        </div>
        <h1 class="login-title">伏 羲</h1>
        <p class="login-subtitle">FuXi v2.1 — 人工智能知识平台</p>
      </div>

      <!-- 双角色 Tab 切换（参考飞书登录风格） -->
      <div class="login-tabs" role="tablist" aria-label="选择登录角色">
        <button
          class="login-tab"
          :class="{ 'login-tab--active': activeRole === 'admin' }"
          role="tab"
          :aria-selected="activeRole === 'admin'"
          @click="switchRole('admin')"
        >
          <el-icon :size="16"><Avatar /></el-icon>
          <span>管理员</span>
        </button>
        <button
          class="login-tab"
          :class="{ 'login-tab--active': activeRole === 'user' }"
          role="tab"
          :aria-selected="activeRole === 'user'"
          @click="switchRole('user')"
        >
          <el-icon :size="16"><User /></el-icon>
          <span>普通用户</span>
        </button>
      </div>

      <!-- 登录表单 -->
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        class="login-form"
        aria-label="登录表单"
        @submit.prevent="handleLogin"
      >
        <!-- 用户名输入框（带抖动动画） -->
        <el-form-item prop="username" :class="{ 'shake-input': shakeUsername }">
          <label for="login-username" class="sr-only">
            {{ activeRole === 'admin' ? '管理员账号' : '用户名' }}
          </label>
          <el-input
            id="login-username"
            v-model="form.username"
            :placeholder="activeRole === 'admin' ? '请输入管理员账号' : '请输入用户名'"
            :prefix-icon="UserFilled"
            size="large"
            clearable
            :aria-label="activeRole === 'admin' ? '管理员账号' : '用户名'"
          />
        </el-form-item>

        <!-- 密码输入框（带抖动动画） -->
        <el-form-item prop="password" :class="{ 'shake-input': shakePassword }">
          <label for="login-password" class="sr-only">密码</label>
          <el-input
            id="login-password"
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            :prefix-icon="Lock"
            size="large"
            show-password
            aria-label="密码"
            @keyup.enter="handleLogin"
          />
        </el-form-item>

        <!-- 登录按钮 -->
        <el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="isLoading"
            class="login-submit-btn"
            @click="handleLogin"
          >
            {{ isLoading ? '登录中...' : activeRole === 'admin' ? '管理员登录' : '用户登录' }}
          </el-button>
        </el-form-item>
      </el-form>

      <!-- 角色提示 -->
      <div class="login-hint">
        <el-icon :size="16"><InfoFilled /></el-icon>
        <span>
          {{
            activeRole === 'admin'
              ? '使用管理员账号登录，可访问系统管理与知识面板'
              : '使用普通用户账号登录，访问知识服务与智能搜索功能'
          }}
        </span>
      </div>

      <!-- 错误提示 -->
      <transition name="fade-slide">
        <div v-if="errorMsg" class="login-error" role="alert">
          <el-icon :size="16"><WarningFilled /></el-icon>
          <span>{{ errorMsg }}</span>
        </div>
      </transition>
    </div>

    <!-- 底部版本信息 -->
    <div class="login-footer">
      <span>伏羲 FuXi v2.1</span>
      <span class="login-footer-divider">·</span>
      <span>基于八卦体系 · 人工智能知识平台</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { User, UserFilled, Lock, WarningFilled, InfoFilled, Avatar } from '@element-plus/icons-vue';
import type { FormInstance, FormRules } from 'element-plus';
import type { LoginResponse } from '@/types';

// ============================================
// 依赖注入
// ============================================
const router = useRouter();
const route = useRoute();
const authStore = useAuthStore();

// ============================================
// 响应式状态
// ============================================
const formRef = ref<FormInstance>();
const isLoading = ref<boolean>(false);
const errorMsg = ref<string>('');
const activeRole = ref<'admin' | 'user'>('admin');
const shakeCard = ref<boolean>(false);
const shakeUsername = ref<boolean>(false);
const shakePassword = ref<boolean>(false);
const loginSuccess = ref<boolean>(false);

// ============================================
// 表单数据
// ============================================
interface LoginForm {
  username: string;
  password: string;
}

const form = reactive<LoginForm>({
  username: '',
  password: '',
});

const rules: FormRules<LoginForm> = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 50, message: '用户名长度在 2 到 50 个字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度至少 6 个字符', trigger: 'blur' },
  ],
};

// ============================================
// 方法
// ============================================

/** 切换角色 */
function switchRole(role: 'admin' | 'user'): void {
  if (activeRole.value === role) return;
  activeRole.value = role;
  errorMsg.value = '';
}

/** 触发卡片抖动（登录失败） */
function triggerShakeCard(): void {
  shakeCard.value = true;
  setTimeout(() => {
    shakeCard.value = false;
  }, 600);
}

/** 触发输入框抖动（登录失败） */
function triggerShakeInputs(): void {
  shakeUsername.value = true;
  shakePassword.value = true;
  setTimeout(() => {
    shakeUsername.value = false;
    shakePassword.value = false;
  }, 600);
}

/** 处理登录 */
async function handleLogin(): Promise<void> {
  if (!formRef.value) return;

  // 表单校验
  try {
    await formRef.value.validate();
  } catch {
    return;
  }

  isLoading.value = true;
  errorMsg.value = '';

  try {
    const loginResponse: LoginResponse = await authStore.login(
      form.username,
      form.password,
      activeRole.value,
    );
    const userRole = loginResponse.user?.role;

    // 角色校验
    if (activeRole.value === 'admin' && userRole !== 'admin') {
      errorMsg.value = '该账号不是管理员账号，请切换到普通用户登录';
      authStore.logout();
      triggerShakeCard();
      triggerShakeInputs();
      return;
    }

    if (activeRole.value === 'user' && userRole === 'admin') {
      errorMsg.value = '该账号是管理员账号，请切换到管理员登录';
      authStore.logout();
      triggerShakeCard();
      triggerShakeInputs();
      return;
    }

    // 登录成功过渡动画
    loginSuccess.value = true;

    // 延迟跳转，等待 fadeOut 动画完成
    setTimeout(() => {
      const redirect = (route.query.redirect as string) || '/';
      router.push(redirect);
    }, 600);
  } catch (err: unknown) {
    const message =
      (err as { response?: { data?: { detail?: string } }; message?: string })?.response?.data
        ?.detail ||
      (err as Error)?.message ||
      '登录失败，请检查账号和密码';

    errorMsg.value = message;
    triggerShakeCard();
    triggerShakeInputs();
  } finally {
    isLoading.value = false;
  }
}
</script>

<style scoped>
/* ============================================
   登录页面 — 小米简约风 + 阴阳双模式
   太极背景旋转动画 + 输入框抖动
   ============================================ */

/* ─── 无障碍：屏幕阅读器专用文本 ─── */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

/* ─── 页面容器 ─── */
.login-page {
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  padding: 24px;
  background-color: var(--fuxi-bg, #FAFAF5);
  transition: background-color 0.6s ease;
  overflow: hidden;
}

.login-page--success {
  background-color: var(--fuxi-bg, #FAFAF5);
}

/* ─── 背景太极 SVG 旋转动画 ─── */
.login-bg-tajii {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  opacity: 0.6;
  pointer-events: none;
  z-index: 0;
}

.login-tajii-svg {
  width: min(80vw, 500px);
  height: min(80vw, 500px);
  animation: tajii-slow-rotate 60s linear infinite;
  transform-origin: center center;
}

@keyframes tajii-slow-rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

/* ─── 登录卡片 ─── */
.login-card {
  position: relative;
  z-index: 1;
  width: 420px;
  max-width: 100%;
  padding: 40px 36px;
  background: var(--fuxi-bg-card, #ffffff);
  border-radius: 12px;
  box-shadow: var(--fuxi-shadow-lg, 0 8px 32px rgba(0, 0, 0, 0.06));
  transition:
    opacity 0.5s ease,
    transform 0.5s ease;
}

/* 卡片抖动动画 */
.login-card--shake {
  animation: card-shake 0.5s ease;
}

@keyframes card-shake {
  0%,
  100% { transform: translateX(0); }
  10%,
  90% { transform: translateX(-4px); }
  30%,
  70% { transform: translateX(6px); }
  50% { transform: translateX(-8px); }
}

/* 卡片淡出 */
.login-card--fadeout {
  opacity: 0;
  transform: translateY(-20px) scale(0.96);
}

/* ─── 品牌标识区 ─── */
.login-brand {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 24px;
}

.login-brand-icon-wrapper {
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 12px;
}

.login-brand-tajii {
  width: 48px;
  height: 48px;
  animation: tajii-slow-rotate 30s linear infinite;
  transform-origin: center center;
}

.login-title {
  font-size: 28px;
  font-weight: 700;
  color: var(--fuxi-text, #333333);
  letter-spacing: 6px;
  margin: 0 0 6px 0;
  font-family: 'PingFang SC', 'Noto Serif SC', serif;
}

.login-subtitle {
  font-size: 13px;
  color: var(--fuxi-text-secondary, #999999);
  margin: 0;
  letter-spacing: 1px;
}

/* ─── 双角色 Tab（参考飞书登录风格） ─── */
.login-tabs {
  display: flex;
  gap: 0;
  margin-bottom: 24px;
  background: var(--fuxi-bg-subtle, #f0ede5);
  border-radius: 10px;
  padding: 3px;
}

.login-tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 9px 0;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--fuxi-text-secondary, #999999);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s ease;
  user-select: none;
}

.login-tab:hover {
  color: var(--fuxi-text, #333333);
}

.login-tab--active {
  background: var(--fuxi-bg-card, #ffffff);
  color: var(--fuxi-primary, #FF6700);
  font-weight: 600;
  box-shadow: var(--fuxi-shadow-sm, 0 1px 6px rgba(0, 0, 0, 0.04));
}

.login-tab--active .el-icon {
  color: var(--fuxi-primary, #FF6700);
}

/* ─── 登录表单 ─── */
.login-form {
  margin-top: 4px;
}

.login-form :deep(.el-form-item) {
  margin-bottom: 18px;
}

.login-form :deep(.el-input__wrapper) {
  background: var(--fuxi-input-bg, #ffffff);
  border: 1px solid var(--fuxi-input-border, #e0e0e0);
  border-radius: 8px;
  box-shadow: none;
  transition:
    border-color 0.3s ease,
    box-shadow 0.3s ease;
}

.login-form :deep(.el-input__wrapper:hover) {
  border-color: var(--fuxi-primary, #FF6700);
}

.login-form :deep(.el-input__wrapper.is-focus) {
  border-color: var(--fuxi-primary, #FF6700);
  box-shadow: 0 0 0 2px rgba(255, 103, 0, 0.15);
}

.login-form :deep(.el-input__prefix) {
  color: var(--fuxi-text-tertiary, #cccccc);
}

.login-form :deep(.el-input__inner) {
  color: var(--fuxi-text, #333333);
}

.login-form :deep(.el-input__inner::placeholder) {
  color: var(--fuxi-text-tertiary, #cccccc);
}

/* ─── 输入框抖动动画 ─── */
.shake-input :deep(.el-input__wrapper) {
  animation: input-shake 0.5s ease;
}

@keyframes input-shake {
  0%,
  100% { transform: translateX(0); }
  10%,
  90% { transform: translateX(-3px); }
  30%,
  70% { transform: translateX(4px); }
  50% { transform: translateX(-6px); }
}

/* ─── 登录按钮 ─── */
.login-submit-btn {
  width: 100%;
  height: 46px;
  font-size: 16px;
  font-weight: 600;
  border-radius: 10px !important;
  border: none;
  background: var(--fuxi-primary-gradient, linear-gradient(135deg, #FF6700, #E55A2B));
  color: #fff;
  transition: all 0.3s ease;
  letter-spacing: 2px;
}

.login-submit-btn:hover {
  opacity: 0.92;
  transform: translateY(-1px);
}

.login-submit-btn:active {
  transform: translateY(0);
}

/* ─── 角色提示 ─── */
.login-hint {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 12px;
  margin-top: 8px;
  background: var(--fuxi-primary-light, #fff3e8);
  border-radius: 8px;
  font-size: 13px;
  color: var(--fuxi-text-secondary, #999999);
  line-height: 1.6;
}

.login-hint .el-icon {
  color: var(--fuxi-primary, #FF6700);
  flex-shrink: 0;
  margin-top: 2px;
}

/* ─── 错误提示 ─── */
.login-error {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 16px;
  padding: 12px;
  background: var(--fuxi-error-bg, rgba(255, 59, 48, 0.08));
  border: 1px solid rgba(255, 59, 48, 0.2);
  border-radius: 8px;
  color: var(--fuxi-error, #ff3b30);
  font-size: 14px;
}

.login-error .el-icon {
  flex-shrink: 0;
}

/* 错误提示过渡 */
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.3s ease;
}

.fade-slide-enter-from,
.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

/* ─── 底部版本信息 ─── */
.login-footer {
  position: absolute;
  bottom: 32px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--fuxi-text-tertiary, #cccccc);
  z-index: 1;
}

.login-footer-divider {
  opacity: 0.4;
}

/* ============================================
   响应式 — 移动端适配
   ============================================ */
@media (max-width: 480px) {
  .login-page {
    padding: 16px;
    justify-content: flex-start;
    padding-top: 80px;
  }

  .login-card {
    width: 100%;
    padding: 32px 20px;
    border-radius: 12px;
  }

  .login-title {
    font-size: 24px;
    letter-spacing: 4px;
  }

  .login-subtitle {
    font-size: 12px;
  }

  .login-tab {
    font-size: 13px;
    padding: 8px 0;
  }

  .login-submit-btn {
    height: 44px;
    font-size: 15px;
  }

  .login-footer {
    bottom: 16px;
    flex-direction: column;
    gap: 2px;
  }

  .login-footer-divider {
    display: none;
  }

  .login-tajii-svg {
    width: min(90vw, 320px);
    height: min(90vw, 320px);
  }
}
</style>
