import { createI18n } from 'vue-i18n';
import zhCN from './zh-CN';
import enUS from './en-US';

// 从 localStorage 读取用户语言偏好，默认中文
const savedLocale = localStorage.getItem('fuxi-locale') || 'zh-CN';

const i18n = createI18n({
  legacy: false, // 使用 Composition API 模式
  locale: savedLocale,
  fallbackLocale: 'zh-CN',
  messages: {
    'zh-CN': zhCN,
    'en-US': enUS,
  },
  globalInjection: true,
});

/**
 * 切换语言
 * @param locale 目标语言代码 ('zh-CN' | 'en-US')
 */
export function setLocale(locale: string): void {
  i18n.global.locale.value = locale;
  localStorage.setItem('fuxi-locale', locale);
  // Element Plus 的语言包切换
  // 动态导入 Element Plus 的语言包（如需要）
  import('element-plus/dist/locale/' + (locale === 'zh-CN' ? 'zh-cn' : 'en') + '.mjs')
    .then(() => {
      // Element Plus 语言已在 main.js 中处理
    })
    .catch(() => {
      // 静默处理
    });
}

export default i18n;
