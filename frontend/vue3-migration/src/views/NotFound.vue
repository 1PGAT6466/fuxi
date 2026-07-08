<template>
  <div class="not-found-page">
    <div class="not-found-content">
      <div class="not-found-code">404</div>
      <h1 class="not-found-title">{{ $t('app.notFound') }}</h1>
      <p class="not-found-desc">{{ $t('app.notFoundDesc') }}</p>
      <div class="not-found-actions">
        <el-button type="primary" size="large" @click="goHome">
          <el-icon><HomeFilled /></el-icon>
          {{ $t('app.backHome') }}
        </el-button>
        <el-button size="large" @click="goBack">
          <el-icon><Back /></el-icon>
          {{ $t('app.backPrev') }}
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router';

const router = useRouter();
const goHome = (): void => {
  router.push('/');
};
const goBack = (): void => {
  router.back();
};
</script>

<style scoped lang="scss">
.not-found-page {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: var(--bg-primary);
}

.not-found-content {
  text-align: center;
  padding: 60px 40px;
}

.not-found-code {
  font-size: 120px;
  font-weight: 800;
  background: var(--fuxi-primary-gradient);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  line-height: 1;
  margin-bottom: 16px;
}

.not-found-title {
  font-size: 24px;
  color: var(--text-primary);
  margin: 0 0 12px;
}

.not-found-desc {
  font-size: 16px;
  color: var(--text-secondary);
  margin: 0 0 32px;
}

.not-found-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
}

/* ───────── 响应式 ───────── */
@media (max-width: 767px) {
  .not-found-code {
    font-size: 60px;
  }

  .not-found-title {
    font-size: 18px;
  }

  .not-found-desc {
    font-size: 14px;
  }

  .not-found-actions {
    flex-direction: column;
    align-items: center;
  }
}
</style>
