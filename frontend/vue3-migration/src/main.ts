import { createApp } from 'vue';
import { createPinia } from 'pinia';
// Element Plus 按需导入：
// - unplugin-vue-components 自动注册模板中使用的组件
// - unplugin-element-plus 自动导入组件样式
// 不再需要全局 app.use(ElementPlus)
import App from './App.vue';
import router from './router';
import i18n from './locales';
import { initOfflineMode } from './services/offline/__init__';
import './styles/variables.css';
import './assets/styles/main.scss';
import './assets/styles/animations.scss';
import './assets/styles/element-dark.scss';

const app = createApp(App);

app.use(createPinia());
app.use(router);
app.use(i18n);
// Element Plus 组件通过 unplugin-vue-components 自动注册
// 不再全局注册，实现按需加载

// 【修复】全局错误边界 — 捕获未处理的组件错误
app.config.errorHandler = (err, _instance, info) => {
  console.error('[伏羲 全局异常]', err, info);
  // 可扩展：上报到监控服务
};

// 初始化离线模式（非阻塞）
initOfflineMode({ initServiceWorker: true }).catch((err) => {
  console.warn('[伏羲] 离线模式初始化失败，降级运行', err);
});

app.mount('#app');
