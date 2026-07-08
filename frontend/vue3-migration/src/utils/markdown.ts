/**
 * 伏羲体系 - Markdown 安全渲染工具
 * 统一所有组件中的 Markdown 渲染逻辑，确保 XSS 防护一致
 */
import { marked } from 'marked';
import DOMPurify from 'dompurify';

/**
 * 安全地将 Markdown 文本渲染为 HTML
 * 自动进行 XSS 清理并添加外部链接安全属性
 * @param content - Markdown 内容
 * @returns 安全的 HTML 字符串
 */
export function renderMarkdown(content: string | null | undefined): string {
  if (!content) return '';

  // 将 Markdown 转为 HTML
  const html: string | Promise<string> = marked(content);
  const htmlStr = typeof html === 'string' ? html : '';

  // 用 DOMPurify 清理 XSS
  const sanitized: string = DOMPurify.sanitize(htmlStr, {
    ADD_ATTR: ['target'],
  });

  // 后处理：给外部链接添加 noopener/noreferrer
  const container = document.createElement('div');
  container.innerHTML = sanitized;
  container.querySelectorAll('a').forEach((link) => {
    if (link.getAttribute('target') === '_blank' || link.hostname !== window.location.hostname) {
      link.setAttribute('rel', 'noopener noreferrer');
      link.setAttribute('target', '_blank');
    }
  });

  return container.innerHTML;
}

export default renderMarkdown;
