<template>
  <!--
    伏羲 v2.1 — 迷你八卦罗盘 SVG 组件
    40×40px，8 卦符号简化为方向短横线
    活跃卦位高亮暖橙 #FF6700，悬停 tooltip，点击跳转九宫格首页
  -->
  <el-tooltip :content="activeGuaName" placement="bottom" :show-after="300">
    <button
      class="mini-bagua-compass"
      aria-label="迷你八卦罗盘，点击返回九宫格首页"
      title="返回九宫格首页"
      @click="goHome"
    >
      <svg
        width="40"
        height="40"
        viewBox="0 0 40 40"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
        role="img"
      >
        <!-- 背景圆 -->
        <circle cx="20" cy="20" r="18" fill="var(--fuxi-bg-subtle, #f0ede5)" stroke="var(--fuxi-border, #eee)" stroke-width="1" />

        <!-- 8 卦简化为 8 方向短横线 -->
        <g stroke-width="1.5" stroke-linecap="round">
          <!-- 乾 ☰ 上（三条阳爻） -->
          <template v-for="i in 3" :key="'qian-' + i">
            <line
              :x1="14" :x2="26"
              :y1="8 + (i - 1) * 3.5"
              :y2="8 + (i - 1) * 3.5"
              :stroke="activeGua === 'qian' ? '#FF6700' : '#999'"
            />
          </template>

          <!-- 坤 ☷ 下（三条阴爻） -->
          <template v-for="i in 3" :key="'kun-' + i">
            <line
              :x1="14" :x2="19"
              :y1="28 + (i - 1) * 3.5"
              :y2="28 + (i - 1) * 3.5"
              :stroke="activeGua === 'kun' ? '#FF6700' : '#999'"
            />
            <line
              :x1="21" :x2="26"
              :y1="28 + (i - 1) * 3.5"
              :y2="28 + (i - 1) * 3.5"
              :stroke="activeGua === 'kun' ? '#FF6700' : '#999'"
            />
          </template>

          <!-- 离 ☲ 左（阳阴阳） -->
          <line :x1="6" :x2="11" :y1="16" :y2="16" :stroke="activeGua === 'li' ? '#FF6700' : '#999'" />
          <line :x1="13" :x2="16" :y1="16" :y2="16" :stroke="activeGua === 'li' ? '#FF6700' : '#999'" />
          <line :x1="6" :x2="16" :y1="20" :y2="20" :stroke="activeGua === 'li' ? '#FF6700' : '#999'" />
          <line :x1="6" :x2="11" :y1="24" :y2="24" :stroke="activeGua === 'li' ? '#FF6700' : '#999'" />
          <line :x1="13" :x2="16" :y1="24" :y2="24" :stroke="activeGua === 'li' ? '#FF6700' : '#999'" />

          <!-- 坎 ☵ 右（阴阳阴） -->
          <line :x1="24" :x2="34" :y1="16" :y2="16" :stroke="activeGua === 'kan' ? '#FF6700' : '#999'" />
          <line :x1="24" :x2="29" :y1="20" :y2="20" :stroke="activeGua === 'kan' ? '#FF6700' : '#999'" />
          <line :x1="31" :x2="34" :y1="20" :y2="20" :stroke="activeGua === 'kan' ? '#FF6700' : '#999'" />
          <line :x1="24" :x2="34" :y1="24" :y2="24" :stroke="activeGua === 'kan' ? '#FF6700' : '#999'" />
        </g>

        <!-- 中心点 -->
        <circle cx="20" cy="20" r="2" fill="#FF6700" opacity="0.8" />
      </svg>
    </button>
  </el-tooltip>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRouter } from 'vue-router';

const router = useRouter();

/** 八卦名称映射 */
const guaNames: Record<string, string> = {
  qian: '☰ 乾 — 知识检索',
  kun: '☷ 坤 — 记忆存储',
  zhen: '☳ 震 — 主动推送',
  xun: '☴ 巽 — 数据管道',
  kan: '☵ 坎 — 安全风控',
  li: '☲ 离 — 知识推理',
  gen: '☶ 艮 — 自愈稳定',
  dui: '☱ 兑 — 对话交互',
};

interface Props {
  /** 当前活跃的卦位 */
  activeGua?: string;
}

const props = withDefaults(defineProps<Props>(), {
  activeGua: 'qian',
});

const activeGuaName = computed(() => guaNames[props.activeGua] ?? guaNames.qian);

function goHome(): void {
  router.push('/');
}
</script>

<style scoped>
.mini-bagua-compass {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border: none;
  background: transparent;
  border-radius: 8px;
  cursor: pointer;
  padding: 0;
  transition: all 0.2s ease;
}

.mini-bagua-compass:hover {
  background: rgba(255, 103, 0, 0.08);
  transform: scale(1.05);
}

.mini-bagua-compass:active {
  transform: scale(0.95);
}

.mini-bagua-compass svg {
  display: block;
}
</style>
