<template>
  <div class="home-page">
    <!-- 欢迎横幅 -->
    <div class="welcome-banner">
      <div class="banner-content">
        <h1 class="banner-title">{{ $t('home.welcomeTitle') }}</h1>
        <p class="banner-desc">{{ $t('home.welcomeDesc') }}</p>
        <div class="banner-actions">
          <el-button type="primary" size="large" @click="navigate('/chat')">
            <el-icon><ChatDotRound /></el-icon> {{ $t('home.startChat') }}
          </el-button>
          <el-button size="large" @click="navigate('/search')">
            <el-icon><Search /></el-icon> {{ $t('home.searchKnowledge') }}
          </el-button>
        </div>
      </div>
    </div>

    <!-- 工具卡片 -->
    <div class="tools-section">
      <h2 class="section-title">{{ $t('home.coreFeatures') }}</h2>
      <el-row :gutter="20">
        <el-col v-for="tool in tools" :key="tool.name" :xs="24" :sm="12" :md="6">
          <el-card class="tool-card" shadow="hover" @click="navigate(tool.route)">
            <div class="tool-icon" :style="{ background: tool.color }">
              <el-icon :size="28">
                <component :is="tool.icon" />
              </el-icon>
            </div>
            <h3 class="tool-name">{{ tool.name }}</h3>
            <p class="tool-desc">{{ tool.desc }}</p>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <!-- FAQ 区 -->
    <div class="faq-section">
      <h2 class="section-title">{{ $t('home.faq') }}</h2>
      <el-collapse accordion>
        <el-collapse-item v-for="faq in faqs" :key="faq.q" :title="faq.q">
          <p class="faq-answer">{{ faq.a }}</p>
        </el-collapse-item>
      </el-collapse>
    </div>

    <!-- 统计面板 -->
    <div v-if="authStore.isAdmin" class="stats-section">
      <h2 class="section-title">{{ $t('home.systemOverview') }}</h2>
      <el-row :gutter="20">
        <el-col v-for="stat in quickStats" :key="stat.label" :xs="12" :sm="6">
          <el-card class="stat-card" shadow="hover">
            <el-statistic :value="stat.value" :title="stat.label" />
          </el-card>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { ChatDotRound, Search } from '@element-plus/icons-vue';
import apiClient from '@/api';

const i18n = useI18n();
const router = useRouter();
const authStore = useAuthStore();

function navigate(path: string): void {
  router.push(path);
}

interface Tool {
  name: string;
  desc: string;
  icon: string;
  route: string;
  color: string;
}

const tools: Tool[] = [
  {
    name: i18n.t('home.tools.chat.name'),
    desc: i18n.t('home.tools.chat.desc'),
    icon: 'ChatDotRound',
    route: '/chat',
    color: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
  },
  {
    name: i18n.t('home.tools.search.name'),
    desc: i18n.t('home.tools.search.desc'),
    icon: 'Search',
    route: '/search',
    color: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
  },
  {
    name: i18n.t('home.tools.files.name'),
    desc: i18n.t('home.tools.files.desc'),
    icon: 'Folder',
    route: '/files',
    color: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
  },
  {
    name: i18n.t('home.tools.admin.name'),
    desc: i18n.t('home.tools.admin.desc'),
    icon: 'Setting',
    route: '/admin',
    color: 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
  },
];

interface FaqItem {
  q: string;
  a: string;
}

const faqs: FaqItem[] = [
  {
    q: i18n.t('home.faqs.0.q'),
    a: i18n.t('home.faqs.0.a'),
  },
  {
    q: i18n.t('home.faqs.1.q'),
    a: i18n.t('home.faqs.1.a'),
  },
  {
    q: i18n.t('home.faqs.2.q'),
    a: i18n.t('home.faqs.2.a'),
  },
  {
    q: i18n.t('home.faqs.3.q'),
    a: i18n.t('home.faqs.3.a'),
  },
];

const quickStats = ref([
  { label: i18n.t('home.documentCount'), value: 0 },
  { label: i18n.t('home.knowledgeEntries'), value: 0 },
  { label: i18n.t('home.todayQueries'), value: 0 },
  { label: i18n.t('home.onlineUsers'), value: 0 },
]);

onMounted(async () => {
  if (authStore.isAdmin) {
    try {
      const data = await apiClient.get('/api/admin/status');
      if (data) {
        quickStats.value = [
          { label: i18n.t('home.documentCount'), value: data.knowledge?.documents || 0 },
          { label: i18n.t('home.knowledgeEntries'), value: data.knowledge?.vectors || 0 },
          { label: i18n.t('home.todayQueries'), value: data.users?.todayQueries || 0 },
          { label: i18n.t('home.onlineUsers'), value: data.users?.online || 0 },
        ];
      }
    } catch {
      // 静默处理
    }
  }
});
</script>

<style scoped lang="scss">
.home-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 20px 40px;
}

// 欢迎横幅
.welcome-banner {
  background: linear-gradient(135deg, #FF6700 0%, #E55A00 100%); // 暖橙渐变 (was #667eea→#764ba2)
  border-radius: 16px;
  padding: 48px 40px;
  margin-bottom: 40px;
  color: white;
  text-align: center;
}

.banner-content {
  max-width: 600px;
  margin: 0 auto;
}

.banner-title {
  font-size: 28px;
  font-weight: 700;
  margin: 0 0 12px;
}

.banner-desc {
  font-size: 16px;
  opacity: 0.85;
  margin: 0 0 24px;
  line-height: 1.6;
}

.banner-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  flex-wrap: wrap;
}

// 工具卡片区
.tools-section {
  margin-bottom: 40px;
}

.section-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 20px;
  padding-left: 12px;
  border-left: 4px solid var(--color-primary);
}

.tool-card {
  margin-bottom: 20px;
  cursor: pointer;
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease;
  text-align: center;
  padding: 12px 0;

  &:hover {
    transform: translateY(-4px);
  }

  .tool-icon {
    width: 56px;
    height: 56px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 16px;
    color: white;
  }

  .tool-name {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0 0 8px;
  }

  .tool-desc {
    font-size: 13px;
    color: var(--text-secondary);
    line-height: 1.5;
    margin: 0;
  }
}

// FAQ 区
.faq-section {
  margin-bottom: 40px;

  .faq-answer {
    color: var(--text-secondary);
    line-height: 1.8;
    padding: 8px 16px;
    margin: 0;
  }
}

// 统计区
.stats-section {
  margin-bottom: 40px;
}

.stat-card {
  margin-bottom: 20px;
  text-align: center;
}

// 响应式
@media (max-width: 768px) {
  .welcome-banner {
    padding: 32px 20px;
  }

  .banner-title {
    font-size: 22px;
  }

  .banner-desc {
    font-size: 14px;
  }

  .section-title {
    font-size: 18px;
  }
}
</style>
