import { createApp } from 'vue';
import { createPinia } from 'pinia';
import ElementPlus from 'element-plus';
import 'element-plus/dist/index.css';
import App from './App.vue';
import router from './router';
import i18n from './locales';
import './styles/variables.css';
import './assets/styles/main.scss';
import './assets/styles/animations.scss';
import './assets/styles/element-dark.scss';

const app = createApp(App);

app.use(createPinia());
app.use(router);
app.use(i18n);
app.use(ElementPlus, { size: 'default' });

// 【修复】全局错误边界 — 捕获未处理的组件错误
app.config.errorHandler = (err, _instance, info) => {
  console.error('[伏羲 全局异常]', err, info);
  // 可扩展：上报到监控服务
};

app.mount('#app');
