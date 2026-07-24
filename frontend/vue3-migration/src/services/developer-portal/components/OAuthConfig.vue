<template>
  <div class="oauth-config">
    <!-- 工具栏 -->
    <div class="oauth-config__toolbar">
      <h3 class="oauth-config__title">OAuth 2.0 应用管理</h3>
      <el-button type="primary" @click="$emit('open-create')">
        <el-icon><Plus /></el-icon>
        注册应用
      </el-button>
    </div>

    <!-- OAuth 2.0 流程说明 -->
    <el-alert
      title="OAuth 2.0 认证流程"
      type="info"
      :closable="true"
      class="oauth-config__flow-hint"
    >
      <div class="oauth-config__flow-steps">
        <div class="oauth-config__flow-step">
          <span class="oauth-config__flow-step-num">1</span>
          <span>注册应用获得 Client ID</span>
        </div>
        <el-icon class="oauth-config__flow-arrow"><ArrowRight /></el-icon>
        <div class="oauth-config__flow-step">
          <span class="oauth-config__flow-step-num">2</span>
          <span>引导用户授权</span>
        </div>
        <el-icon class="oauth-config__flow-arrow"><ArrowRight /></el-icon>
        <div class="oauth-config__flow-step">
          <span class="oauth-config__flow-step-num">3</span>
          <span>获取 Authorization Code</span>
        </div>
        <el-icon class="oauth-config__flow-arrow"><ArrowRight /></el-icon>
        <div class="oauth-config__flow-step">
          <span class="oauth-config__flow-step-num">4</span>
          <span>换取 Access Token</span>
        </div>
        <el-icon class="oauth-config__flow-arrow"><ArrowRight /></el-icon>
        <div class="oauth-config__flow-step">
          <span class="oauth-config__flow-step-num">5</span>
          <span>调用 API</span>
        </div>
      </div>
    </el-alert>

    <!-- Loading -->
    <div v-if="loading" class="oauth-config__loading">
      <el-skeleton :rows="4" animated />
    </div>

    <!-- Error -->
    <el-alert
      v-else-if="error"
      :title="error"
      type="error"
      show-icon
      :closable="false"
      class="oauth-config__error"
    >
      <template #default>
        <el-button size="small" type="primary" link @click="$emit('refresh')">重试</el-button>
      </template>
    </el-alert>

    <!-- 应用列表 -->
    <div v-else class="oauth-config__app-list">
      <div
        v-for="app in apps"
        :key="app.id"
        class="oauth-config__app-card"
      >
        <div class="oauth-config__app-card-header">
          <div class="oauth-config__app-card-info">
            <span class="oauth-config__app-card-name">{{ app.name }}</span>
            <el-tag
              size="small"
              :type="app.status === 'active' ? 'success' : app.status === 'revoked' ? 'danger' : 'warning'"
            >
              {{ app.status === 'active' ? '活跃' : app.status === 'revoked' ? '已撤销' : '待审核' }}
            </el-tag>
          </div>
          <span class="oauth-config__app-card-date">创建于 {{ app.createdAt }}</span>
        </div>

        <p v-if="app.description" class="oauth-config__app-card-desc">{{ app.description }}</p>

        <div class="oauth-config__app-card-details">
          <div class="oauth-config__app-card-field">
            <span class="oauth-config__app-card-field-label">Client ID</span>
            <code class="oauth-config__app-card-field-value">{{ app.clientId }}</code>
            <el-button size="small" text @click="copyToClipboard(app.clientId)">
              <el-icon><CopyDocument /></el-icon>
            </el-button>
          </div>

          <div class="oauth-config__app-card-field">
            <span class="oauth-config__app-card-field-label">回调 URI</span>
            <div class="oauth-config__app-card-uris">
              <code v-for="uri in app.redirectUris" :key="uri">{{ uri }}</code>
            </div>
          </div>

          <div class="oauth-config__app-card-field">
            <span class="oauth-config__app-card-field-label">授权类型</span>
            <div class="oauth-config__app-card-tags">
              <el-tag
                v-for="type in app.grantTypes"
                :key="type"
                size="small"
                effect="plain"
              >
                {{ OAUTH_GRANT_LABELS[type] }}
              </el-tag>
            </div>
          </div>

          <div class="oauth-config__app-card-field">
            <span class="oauth-config__app-card-field-label">权限范围</span>
            <div class="oauth-config__app-card-tags">
              <el-tag
                v-for="scope in app.scopes"
                :key="scope"
                size="small"
                effect="plain"
                type="info"
              >
                {{ scope }}
              </el-tag>
            </div>
          </div>
        </div>
      </div>

      <el-empty v-if="!apps.length" description="暂无已注册的 OAuth 应用" />
    </div>

    <!-- ────── 创建应用弹窗 ────── -->
    <el-dialog
      v-model="showCreateDialogProxy"
      title="注册 OAuth 2.0 应用"
      width="580px"
      :close-on-click-modal="false"
      @close="$emit('close-create')"
    >
      <el-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        label-width="100px"
        label-position="top"
      >
        <el-form-item label="应用名称" prop="name">
          <el-input v-model="formData.name" placeholder="输入应用名称" maxlength="50" show-word-limit />
        </el-form-item>
        <el-form-item label="应用描述" prop="description">
          <el-input
            v-model="formData.description"
            type="textarea"
            :rows="2"
            placeholder="简要描述应用用途"
            maxlength="200"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="回调 URI" prop="redirectUris">
          <div class="oauth-config__uri-inputs">
            <div
              v-for="(uri, idx) in formData.redirectUris"
              :key="idx"
              class="oauth-config__uri-row"
            >
              <el-input v-model="formData.redirectUris[idx]" placeholder="https://example.com/callback" />
              <el-button
                v-if="formData.redirectUris.length > 1"
                type="danger"
                text
                @click="removeUri(idx)"
              >
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
            <el-button size="small" text type="primary" @click="addUri">
              <el-icon><Plus /></el-icon>
              添加回调 URI
            </el-button>
          </div>
        </el-form-item>
        <el-form-item label="授权类型" prop="grantTypes">
          <el-checkbox-group v-model="formData.grantTypes">
            <el-checkbox
              v-for="gt in grantTypeOptions"
              :key="gt.value"
              :label="gt.value"
              :value="gt.value"
            >
              {{ gt.label }}
            </el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="权限范围" prop="scopes">
          <el-checkbox-group v-model="formData.scopes">
            <div class="oauth-config__scopes-grid">
              <el-checkbox
                v-for="s in availableScopes"
                :key="s.value"
                :label="s.value"
                :value="s.value"
              >
                <span class="oauth-config__scope-label">{{ s.label }}</span>
                <span class="oauth-config__scope-desc">{{ s.description }}</span>
              </el-checkbox>
            </div>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="应用主页" prop="homepageUrl">
          <el-input v-model="formData.homepageUrl" placeholder="https://example.com" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="$emit('close-create')">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">注册应用</el-button>
      </template>
    </el-dialog>

    <!-- ────── 新应用 Secret 弹窗 ────── -->
    <el-dialog
      v-model="showNewAppModalProxy"
      title="应用注册成功"
      width="480px"
      :close-on-click-modal="false"
      @close="$emit('close-new-modal')"
    >
      <el-alert
        title="请立即保存 Client Secret，关闭后将无法再次查看！"
        type="warning"
        :closable="false"
        show-icon
      />
      <div v-if="lastCreatedApp" class="oauth-config__new-app-info">
        <div class="oauth-config__new-app-field">
          <span class="oauth-config__new-app-field-label">Client ID</span>
          <code>{{ lastCreatedApp.clientId }}</code>
        </div>
        <div class="oauth-config__new-app-field">
          <span class="oauth-config__new-app-field-label">Client Secret</span>
          <div class="oauth-config__new-app-secret">
            <code>{{ lastCreatedApp.clientSecret }}</code>
            <el-button
              size="small"
              type="primary"
              @click="lastCreatedApp.clientSecret && copyToClipboard(lastCreatedApp.clientSecret)"
            >
              复制
            </el-button>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button type="primary" @click="$emit('close-new-modal')">我已保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
/**
 * OAuth 2.0 认证配置 — 应用注册与管理
 */
import { ref, computed } from 'vue';
import { ElMessage, type FormInstance, type FormRules } from 'element-plus';
import {
  Plus,
  ArrowRight,
  CopyDocument,
  Delete,
} from '@element-plus/icons-vue';
import type { OAuthApp, OAuthGrantType, CreateOAuthAppRequest } from '../types';
import { OAUTH_GRANT_LABELS, OAUTH_SCOPES } from '../types';

const props = defineProps<{
  apps: OAuthApp[];
  loading: boolean;
  error: string | null;
  showCreateDialog: boolean;
  lastCreatedApp: OAuthApp | null;
  showNewAppModal: boolean;
}>();

const emit = defineEmits<{
  'open-create': [];
  'close-create': [];
  'create-app': [data: CreateOAuthAppRequest];
  'close-new-modal': [];
  refresh: [];
}>();

// 弹窗双向绑定
const showCreateDialogProxy = computed({
  get: () => props.showCreateDialog,
  set: (val) => { if (!val) emit('close-create'); },
});

const showNewAppModalProxy = computed({
  get: () => props.showNewAppModal,
  set: (val) => { if (!val) emit('close-new-modal'); },
});

// 表单
const formRef = ref<FormInstance>();
const submitting = ref(false);

const formData = ref<CreateOAuthAppRequest>({
  name: '',
  description: '',
  redirectUris: [''],
  grantTypes: ['authorization_code', 'refresh_token'],
  scopes: ['read:documents', 'chat:send'],
  homepageUrl: '',
});

const formRules: FormRules = {
  name: [
    { required: true, message: '请输入应用名称', trigger: 'blur' },
    { min: 2, max: 50, message: '名称长度在 2~50 个字符', trigger: 'blur' },
  ],
  redirectUris: [
    {
      validator: (_rule, value: string[]) => {
        const hasValid = value.some((v) => v.trim().length > 0);
        return hasValid ? Promise.resolve() : Promise.reject(new Error('至少需要一个回调 URI'));
      },
      trigger: 'blur',
    },
  ],
  grantTypes: [
    {
      validator: (_rule, value: string[]) => {
        return value.length > 0 ? Promise.resolve() : Promise.reject(new Error('至少选择一种授权类型'));
      },
      trigger: 'change',
    },
  ],
  homepageUrl: [
    { type: 'url', message: '请输入有效的 URL', trigger: 'blur', required: false },
  ],
};

const grantTypeOptions = Object.entries(OAUTH_GRANT_LABELS).map(([value, label]) => ({ value, label }));
const availableScopes = OAUTH_SCOPES;

function addUri(): void {
  formData.value.redirectUris.push('');
}

function removeUri(idx: number): void {
  formData.value.redirectUris.splice(idx, 1);
}

async function handleSubmit(): Promise<void> {
  if (!formRef.value) return;
  try {
    await formRef.value.validate();
  } catch {
    return;
  }
  submitting.value = true;
  const data: CreateOAuthAppRequest = {
    ...formData.value,
    redirectUris: formData.value.redirectUris.filter((u) => u.trim()),
  };
  emit('create-app', data);
  // Reset form
  formData.value = {
    name: '',
    description: '',
    redirectUris: [''],
    grantTypes: ['authorization_code', 'refresh_token'],
    scopes: ['read:documents', 'chat:send'],
    homepageUrl: '',
  };
  submitting.value = false;
}

async function copyToClipboard(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text);
    ElMessage.success('已复制到剪贴板');
  } catch {
    ElMessage.error('复制失败，请手动复制');
  }
}
</script>

<style scoped lang="scss">
.oauth-config {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.oauth-config__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.oauth-config__title {
  font-size: 17px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.oauth-config__flow-hint {
  margin-bottom: 4px;
}

.oauth-config__flow-steps {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  flex-wrap: wrap;
}

.oauth-config__flow-step {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-secondary);
}

.oauth-config__flow-step-num {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--brand);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}

.oauth-config__flow-arrow {
  color: var(--text-tertiary);
}

.oauth-config__loading,
.oauth-config__error {
  padding: 16px 0;
}

/* ── 应用卡片 ── */
.oauth-config__app-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.oauth-config__app-card {
  padding: 16px 20px;
  background: var(--bg-subtle);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-color);
}

.oauth-config__app-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.oauth-config__app-card-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.oauth-config__app-card-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.oauth-config__app-card-date {
  font-size: 12px;
  color: var(--text-tertiary);
}

.oauth-config__app-card-desc {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0 0 12px;
}

.oauth-config__app-card-details {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.oauth-config__app-card-field {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
}

.oauth-config__app-card-field-label {
  font-weight: 600;
  color: var(--text-secondary);
  min-width: 70px;
  flex-shrink: 0;
  padding-top: 2px;
}

.oauth-config__app-card-field-value {
  font-family: monospace;
  font-size: 12px;
  background: var(--bg-card);
  padding: 2px 8px;
  border-radius: 4px;
}

.oauth-config__app-card-uris {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;

  code {
    font-family: monospace;
    font-size: 12px;
    background: var(--bg-card);
    padding: 2px 8px;
    border-radius: 4px;
    color: var(--text-primary);
  }
}

.oauth-config__app-card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

/* ── 创建弹窗 ── */
.oauth-config__uri-inputs {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.oauth-config__uri-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.oauth-config__scopes-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
}

.oauth-config__scope-label {
  font-weight: 600;
  font-size: 13px;
}

.oauth-config__scope-desc {
  font-size: 11px;
  color: var(--text-tertiary);
  margin-left: 20px;
}

/* ── 新应用 Secret 弹窗 ── */
.oauth-config__new-app-info {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.oauth-config__new-app-field {
  code {
    font-family: monospace;
    font-size: 14px;
    background: var(--bg-subtle);
    padding: 6px 12px;
    border-radius: 4px;
    display: inline-block;
    margin-top: 4px;
  }
}

.oauth-config__new-app-field-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.oauth-config__new-app-secret {
  display: flex;
  align-items: center;
  gap: 8px;

  code {
    margin-top: 0;
  }
}
</style>
