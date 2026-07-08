/**
 * 伏羲体系 - 通用工具函数
 * 提取重复的格式化、评分判断等逻辑到统一位置
 */

/**
 * 格式化文件大小
 * @param bytes - 文件字节数
 * @returns 人类可读的文件大小字符串
 */
export function formatSize(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined || isNaN(bytes)) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  let size: number = Math.abs(Number(bytes));
  let unitIndex: number = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex++;
  }
  const sign = Number(bytes) < 0 ? '-' : '';
  return `${sign}${size.toFixed(1)} ${units[unitIndex]}`;
}

/**
 * 格式化日期时间（完整）
 * @param dateString - 日期字符串、时间戳或 Date 对象
 * @returns 格式化后的完整日期时间字符串
 */
export function formatDate(dateString: string | number | Date): string {
  if (!dateString) return '';
  return new Date(dateString).toLocaleString('zh-CN');
}

/**
 * 格式化仅日期
 * @param dateString - 日期字符串、时间戳或 Date 对象
 * @returns 格式化后的日期字符串（YYYY/MM/DD）
 */
export function formatDateOnly(dateString: string | number | Date): string {
  if (!dateString) return '';
  return new Date(dateString).toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  });
}

/**
 * 获取百分比分数对应的 Element Plus tag 类型（0-100 分数）
 * @param score - 0-100 之间的分数
 * @returns Element Plus tag 类型 'success' | 'warning' | 'danger'
 */
export function getPercentScoreType(score: number): 'success' | 'warning' | 'danger' {
  if (score >= 80) return 'success';
  if (score >= 60) return 'warning';
  return 'danger';
}

/**
 * 获取 0-1 小数分数对应的 Element Plus tag 类型
 * @param score - 0-1 之间的分数
 * @returns Element Plus tag 类型 'success' | 'warning' | 'info'
 */
export function getScoreType(score: number): 'success' | 'warning' | 'info' {
  if (score >= 0.8) return 'success';
  if (score >= 0.6) return 'warning';
  return 'info';
}

/**
 * 格式化时间戳为 HH:MM 格式
 * @param timestamp - Unix 毫秒时间戳
 * @returns HH:MM 格式的时间字符串
 */
export function formatTime(timestamp: number): string {
  if (!timestamp) return '';
  return new Date(timestamp).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  });
}
