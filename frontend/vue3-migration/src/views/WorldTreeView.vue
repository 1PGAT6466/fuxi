<template>
  <div class="worldtree-view">
    <div class="worldtree-header">
      <h2>世界树</h2>
      <p class="worldtree-desc">数据管道与信息流转的根脉系统</p>
    </div>

    <div class="worldtree-placeholder">
      <div class="worldtree-placeholder__icon">
        <svg width="80" height="80" viewBox="0 0 80 80" fill="none">
          <rect x="36" y="5" width="8" height="16" rx="2" fill="var(--zhen-color)" opacity="0.8" />
          <rect x="30" y="18" width="20" height="6" rx="2" fill="var(--zhen-color)" opacity="0.6" />
          <rect x="28" y="30" width="24" height="6" rx="2" fill="var(--xun-color)" opacity="0.6" />
          <rect x="24" y="42" width="32" height="6" rx="2" fill="var(--kan-color)" opacity="0.6" />
          <rect x="20" y="54" width="40" height="6" rx="2" fill="var(--kan-color)" opacity="0.4" />
          <rect
            x="32"
            y="22"
            width="4"
            height="12"
            rx="1"
            fill="var(--text-tertiary)"
            opacity="0.4"
          />
          <rect
            x="37"
            y="36"
            width="6"
            height="6"
            rx="1"
            fill="var(--text-tertiary)"
            opacity="0.3"
          />
        </svg>
      </div>
      <h3>世界树</h3>
      <p>数据精炼 · 管道编排 · 信息流转</p>
      <el-tag type="info" effect="plain">即将上线</el-tag>
    </div>
  </div>
</template>

<script setup lang="ts">
// WorldTreeView — 世界树数据管道页面（占位）
</script>

<style scoped>
.worldtree-view {
  max-width: 1200px;
  margin: 0 auto;
  padding: 40px 24px;
}

.worldtree-header {
  margin-bottom: 32px;
}

.worldtree-header h2 {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 8px;
}

.worldtree-desc {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0;
}

.worldtree-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  gap: 16px;
}

.worldtree-placeholder__icon {
  opacity: 0.6;
}

.worldtree-placeholder h3 {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.worldtree-placeholder p {
  font-size: 14px;
  color: var(--text-tertiary);
  margin: 0;
}
</style>
