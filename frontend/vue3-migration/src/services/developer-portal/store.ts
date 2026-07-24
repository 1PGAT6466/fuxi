/**
 * 伏羲 v2.1 — 开发者门户 Store
 *
 * 管理 API 文档、SDK 列表、OAuth 应用、社区帖子的状态缓存
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type {
  ApiDocVersion,
  ApiEndpointGroup,
  OpenApiDoc,
  SdkInfo,
  SdkLanguage,
  OAuthApp,
  CommunityPost,
  CommunityCategory,
} from './types';

export const useDeveloperPortalStore = defineStore('developerPortal', () => {
  // ───── API 文档 ─────
  const apiVersions = ref<ApiDocVersion[]>([]);
  const currentApiVersion = ref<string>('');
  const apiDoc = ref<OpenApiDoc | null>(null);
  const apiGroups = ref<ApiEndpointGroup[]>([]);
  const apiDocLoading = ref<boolean>(false);
  const apiDocError = ref<string | null>(null);

  // ───── SDK ─────
  const sdks = ref<SdkInfo[]>([]);
  const sdkLoading = ref<boolean>(false);
  const sdkError = ref<string | null>(null);
  const selectedSdkLanguage = ref<SdkLanguage | null>(null);

  // ───── OAuth ─────
  const oauthApps = ref<OAuthApp[]>([]);
  const oauthLoading = ref<boolean>(false);
  const oauthError = ref<string | null>(null);
  const showCreateAppDialog = ref<boolean>(false);
  const lastCreatedApp = ref<OAuthApp | null>(null);
  const showNewAppModal = ref<boolean>(false);

  // ───── 社区 ─────
  const communityPosts = ref<CommunityPost[]>([]);
  const communityTotal = ref<number>(0);
  const communityLoading = ref<boolean>(false);
  const communityError = ref<string | null>(null);
  const communityPage = ref<number>(1);
  const communityPageSize = ref<number>(10);
  const selectedCommunityCategory = ref<CommunityCategory | null>(null);

  // ───── 全局 ─────
  const activeTab = ref<string>('api-docs');

  // ───── Getters ─────

  const pythonSdk = computed<SdkInfo | null>(() =>
    sdks.value.find((s) => s.language === 'python') || null,
  );

  const javascriptSdk = computed<SdkInfo | null>(() =>
    sdks.value.find((s) => s.language === 'javascript') || null,
  );

  const javaSdk = computed<SdkInfo | null>(() =>
    sdks.value.find((s) => s.language === 'java') || null,
  );

  const activeOAuthAppCount = computed<number>(() =>
    oauthApps.value.filter((a) => a.status === 'active').length,
  );

  const pinnedPosts = computed<CommunityPost[]>(() =>
    communityPosts.value.filter((p) => p.pinned),
  );

  const filteredPosts = computed<CommunityPost[]>(() => {
    if (!selectedCommunityCategory.value) return communityPosts.value;
    return communityPosts.value.filter(
      (p) => p.category === selectedCommunityCategory.value,
    );
  });

  // ───── Actions ─────

  /** 设置 API 版本列表 */
  function setApiVersions(versions: ApiDocVersion[], currentVersion: string): void {
    apiVersions.value = versions;
    currentApiVersion.value = currentVersion;
    apiDocError.value = null;
  }

  /** 设置 API 文档内容 */
  function setApiDoc(doc: OpenApiDoc, groups: ApiEndpointGroup[]): void {
    apiDoc.value = doc;
    apiGroups.value = groups;
    apiDocError.value = null;
  }

  /** 设置 SDK 列表 */
  function setSdks(list: SdkInfo[]): void {
    sdks.value = list;
    sdkError.value = null;
  }

  /** 设置 OAuth 应用列表 */
  function setOAuthApps(apps: OAuthApp[]): void {
    oauthApps.value = apps;
    oauthError.value = null;
  }

  /** 添加 OAuth 应用 */
  function addOAuthApp(app: OAuthApp): void {
    oauthApps.value.unshift(app);
  }

  /** 设置社区帖子 */
  function setCommunityPosts(posts: CommunityPost[], total: number, page: number): void {
    communityPosts.value = posts;
    communityTotal.value = total;
    communityPage.value = page;
    communityError.value = null;
  }

  /** 选择 SDK 语言 */
  function selectSdkLanguage(lang: SdkLanguage | null): void {
    selectedSdkLanguage.value = lang;
  }

  /** 选择社区分类 */
  function selectCommunityCategory(cat: CommunityCategory | null): void {
    selectedCommunityCategory.value = cat;
    communityPage.value = 1;
  }

  /** 显示创建 OAuth 应用弹窗 */
  function openCreateAppDialog(): void {
    showCreateAppDialog.value = true;
  }

  /** 关闭创建 OAuth 应用弹窗 */
  function closeCreateAppDialog(): void {
    showCreateAppDialog.value = false;
  }

  /** 设置新创建的 OAuth 应用（显示 clientSecret） */
  function setLastCreatedApp(app: OAuthApp): void {
    lastCreatedApp.value = app;
    showNewAppModal.value = true;
  }

  /** 关闭新应用显示弹窗 */
  function closeNewAppModal(): void {
    showNewAppModal.value = false;
    lastCreatedApp.value = null;
  }

  return {
    // 状态
    apiVersions,
    currentApiVersion,
    apiDoc,
    apiGroups,
    apiDocLoading,
    apiDocError,
    sdks,
    sdkLoading,
    sdkError,
    selectedSdkLanguage,
    oauthApps,
    oauthLoading,
    oauthError,
    showCreateAppDialog,
    lastCreatedApp,
    showNewAppModal,
    communityPosts,
    communityTotal,
    communityLoading,
    communityError,
    communityPage,
    communityPageSize,
    selectedCommunityCategory,
    activeTab,

    // Getters
    pythonSdk,
    javascriptSdk,
    javaSdk,
    activeOAuthAppCount,
    pinnedPosts,
    filteredPosts,

    // Actions
    setApiVersions,
    setApiDoc,
    setSdks,
    setOAuthApps,
    addOAuthApp,
    setCommunityPosts,
    selectSdkLanguage,
    selectCommunityCategory,
    openCreateAppDialog,
    closeCreateAppDialog,
    setLastCreatedApp,
    closeNewAppModal,
  };
});
