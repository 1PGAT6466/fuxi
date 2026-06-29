/**
 * @fileoverview 通用工具函数
 * @module utils
 */

/**
 * HTML 转义（防 XSS）
 * @param {string} s - 原始文本
 * @returns {string} 转义后的安全 HTML
 */
function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
