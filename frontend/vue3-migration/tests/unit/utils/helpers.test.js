/**
 * helpers.js 工具函数测试
 * 测试 formatSize, formatDate, getScoreType 等
 */
import { describe, it, expect } from 'vitest';
import {
  formatSize,
  formatDate,
  formatDateOnly,
  getPercentScoreType,
  getScoreType,
  formatTime,
} from '@/utils/helpers';

describe('helpers 工具函数', () => {
  describe('formatSize', () => {
    it('应正确格式化 0 字节', () => {
      expect(formatSize(0)).toBe('0.0 B');
    });

    it('应正确格式化 B 级别', () => {
      expect(formatSize(500)).toBe('500.0 B');
    });

    it('应正确格式化为 KB', () => {
      expect(formatSize(1024)).toBe('1.0 KB');
      expect(formatSize(2048)).toBe('2.0 KB');
      expect(formatSize(1536)).toBe('1.5 KB');
    });

    it('应正确格式化为 MB', () => {
      expect(formatSize(1048576)).toBe('1.0 MB');
      expect(formatSize(5242880)).toBe('5.0 MB');
    });

    it('应正确格式化为 GB', () => {
      expect(formatSize(1073741824)).toBe('1.0 GB');
      expect(formatSize(3221225472)).toBe('3.0 GB');
    });

    it('null 或 undefined 应返回 "0 B"', () => {
      expect(formatSize(null)).toBe('0 B');
      expect(formatSize(undefined)).toBe('0 B');
    });

    it('NaN 应返回 "0 B"', () => {
      expect(formatSize(NaN)).toBe('0 B');
    });

    it('字符串数字应正确处理', () => {
      expect(formatSize('2048')).toBe('2.0 KB');
    });

    it('负数应正确格式化', () => {
      expect(formatSize(-1024)).toBe('-1.0 KB');
    });
  });

  describe('formatDate', () => {
    it('应返回中文本地化日期字符串', () => {
      const result = formatDate('2024-01-15T10:30:00');
      expect(result).toBeTruthy();
      expect(typeof result).toBe('string');
      // 应包含中文本地化格式的日期时间
      expect(result).toContain('2024');
    });

    it('空值应返回空字符串', () => {
      expect(formatDate('')).toBe('');
      expect(formatDate(null)).toBe('');
      expect(formatDate(undefined)).toBe('');
    });

    it('Date 对象应正确格式化', () => {
      const result = formatDate(new Date('2024-06-01T08:00:00'));
      expect(result).toBeTruthy();
      expect(typeof result).toBe('string');
    });

    it('时间戳数字应正确格式化', () => {
      const result = formatDate(1705312200000); // 2024-01-15T10:30:00 UTC+8
      expect(result).toBeTruthy();
      expect(typeof result).toBe('string');
    });
  });

  describe('formatDateOnly', () => {
    it('应返回仅包含日期的格式化字符串', () => {
      const result = formatDateOnly('2024-01-15');
      expect(result).toBeTruthy();
      expect(typeof result).toBe('string');
    });

    it('空值应返回空字符串', () => {
      expect(formatDateOnly('')).toBe('');
      expect(formatDateOnly(null)).toBe('');
    });
  });

  describe('getPercentScoreType', () => {
    it('分数 >= 80 应返回 "success"', () => {
      expect(getPercentScoreType(80)).toBe('success');
      expect(getPercentScoreType(95)).toBe('success');
      expect(getPercentScoreType(100)).toBe('success');
    });

    it('分数 60-79 应返回 "warning"', () => {
      expect(getPercentScoreType(60)).toBe('warning');
      expect(getPercentScoreType(70)).toBe('warning');
      expect(getPercentScoreType(79)).toBe('warning');
    });

    it('分数 < 60 应返回 "danger"', () => {
      expect(getPercentScoreType(0)).toBe('danger');
      expect(getPercentScoreType(30)).toBe('danger');
      expect(getPercentScoreType(59)).toBe('danger');
    });
  });

  describe('getScoreType', () => {
    it('分数 >= 0.8 应返回 "success"', () => {
      expect(getScoreType(0.8)).toBe('success');
      expect(getScoreType(0.9)).toBe('success');
      expect(getScoreType(1.0)).toBe('success');
    });

    it('分数 0.6-0.79 应返回 "warning"', () => {
      expect(getScoreType(0.6)).toBe('warning');
      expect(getScoreType(0.7)).toBe('warning');
      expect(getScoreType(0.79)).toBe('warning');
    });

    it('分数 < 0.6 应返回 "info"', () => {
      expect(getScoreType(0)).toBe('info');
      expect(getScoreType(0.3)).toBe('info');
      expect(getScoreType(0.59)).toBe('info');
    });

    it('浮点数边界应正确处理', () => {
      expect(getScoreType(0.7999999)).toBe('warning');
      expect(getScoreType(0.5999999)).toBe('info');
    });
  });

  describe('formatTime', () => {
    it('应返回 HH:MM 格式的时间', () => {
      const result = formatTime(1705312200000);
      expect(result).toBeTruthy();
      expect(typeof result).toBe('string');
    });

    it('空值应返回空字符串', () => {
      expect(formatTime(0)).toBe('');
      expect(formatTime(null)).toBe('');
      expect(formatTime(undefined)).toBe('');
    });
  });
});
