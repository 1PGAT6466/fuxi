/**
 * 伏羲 v2.1 — DXF 查看器 Mock 数据
 * 提供简单的矩形/线/圆数据用于 Canvas 渲染测试
 */

import type { DxfHealthResponse, DxfFile, DxfRenderData, DxfEntity, DxfLayer } from './types';

// ───── 常量 ─────

const FILE_LIST: DxfFile[] = [
  {
    id: '1',
    hash: 'dxf_sample_1',
    name: '机械零件图_A001.dxf',
    size: 245760,
    uploaded_at: '2026-06-15T08:30:00Z',
    layers_count: 5,
  },
  {
    id: '2',
    hash: 'dxf_sample_2',
    name: '建筑平面图_B102.dxf',
    size: 512000,
    uploaded_at: '2026-06-20T14:15:00Z',
    layers_count: 8,
  },
  {
    id: '3',
    hash: 'dxf_sample_3',
    name: '电路原理图_C205.dxf',
    size: 128000,
    uploaded_at: '2026-07-01T10:45:00Z',
    layers_count: 3,
  },
];

// ───── 渲染数据生成（基于 hash 返回不同内容） ─────

function generateEntities(hash: string): DxfEntity[] {
  switch (hash) {
    case 'dxf_sample_1': // 机械零件图
      return [
        // 外框矩形
        {
          type: 'RECT',
          min: { x: 0, y: 0 },
          max: { x: 400, y: 300 },
          color: '#666666',
          layer: '0',
        },
        // 中心圆孔
        {
          type: 'CIRCLE',
          center: { x: 200, y: 150 },
          radius: 50,
          color: '#FF4500',
          layer: 'holes',
        },
        // 4 个螺孔
        { type: 'CIRCLE', center: { x: 50, y: 50 }, radius: 15, color: '#FF4500', layer: 'holes' },
        { type: 'CIRCLE', center: { x: 350, y: 50 }, radius: 15, color: '#FF4500', layer: 'holes' },
        { type: 'CIRCLE', center: { x: 50, y: 250 }, radius: 15, color: '#FF4500', layer: 'holes' },
        {
          type: 'CIRCLE',
          center: { x: 350, y: 250 },
          radius: 15,
          color: '#FF4500',
          layer: 'holes',
        },
        // 加强筋线
        {
          type: 'LINE',
          start: { x: 100, y: 150 },
          end: { x: 150, y: 150 },
          color: '#00AA00',
          layer: 'ribs',
        },
        {
          type: 'LINE',
          start: { x: 250, y: 150 },
          end: { x: 300, y: 150 },
          color: '#00AA00',
          layer: 'ribs',
        },
        // 标注文字
        {
          type: 'TEXT',
          position: { x: 180, y: 280 },
          content: 'M16x1.5',
          height: 14,
          color: '#333333',
          layer: 'dimensions',
        },
        {
          type: 'TEXT',
          position: { x: 30, y: 280 },
          content: 'A-A',
          height: 12,
          color: '#333333',
          layer: 'dimensions',
        },
        // 斜线装饰
        {
          type: 'LINE',
          start: { x: 0, y: 0 },
          end: { x: 400, y: 300 },
          color: '#CCCCCC',
          layer: 'guide',
        },
      ];

    case 'dxf_sample_2': // 建筑平面图
      return [
        // 外墙
        {
          type: 'RECT',
          min: { x: 0, y: 0 },
          max: { x: 500, y: 400 },
          color: '#333333',
          layer: 'walls',
        },
        // 内墙
        {
          type: 'LINE',
          start: { x: 250, y: 0 },
          end: { x: 250, y: 400 },
          color: '#666666',
          layer: 'walls',
        },
        {
          type: 'LINE',
          start: { x: 0, y: 200 },
          end: { x: 500, y: 200 },
          color: '#666666',
          layer: 'walls',
        },
        // 门洞
        {
          type: 'LINE',
          start: { x: 220, y: 200 },
          end: { x: 220, y: 300 },
          color: '#00AAFF',
          layer: 'doors',
        },
        {
          type: 'LINE',
          start: { x: 280, y: 200 },
          end: { x: 280, y: 300 },
          color: '#00AAFF',
          layer: 'doors',
        },
        {
          type: 'LINE',
          start: { x: 100, y: 200 },
          end: { x: 180, y: 280 },
          color: '#00AAFF',
          layer: 'doors',
        },
        // 窗户
        {
          type: 'LINE',
          start: { x: 50, y: 0 },
          end: { x: 150, y: 0 },
          color: '#00BBFF',
          layer: 'windows',
        },
        {
          type: 'LINE',
          start: { x: 350, y: 400 },
          end: { x: 450, y: 400 },
          color: '#00BBFF',
          layer: 'windows',
        },
        // 柱子
        {
          type: 'RECT',
          min: { x: 0, y: 0 },
          max: { x: 20, y: 20 },
          color: '#888888',
          layer: 'columns',
        },
        {
          type: 'RECT',
          min: { x: 480, y: 0 },
          max: { x: 500, y: 20 },
          color: '#888888',
          layer: 'columns',
        },
        {
          type: 'RECT',
          min: { x: 0, y: 380 },
          max: { x: 20, y: 400 },
          color: '#888888',
          layer: 'columns',
        },
        {
          type: 'RECT',
          min: { x: 480, y: 380 },
          max: { x: 500, y: 400 },
          color: '#888888',
          layer: 'columns',
        },
        {
          type: 'RECT',
          min: { x: 230, y: 180 },
          max: { x: 270, y: 220 },
          color: '#888888',
          layer: 'columns',
        },
        // 房间标注
        {
          type: 'TEXT',
          position: { x: 50, y: 100 },
          content: '客厅 45㎡',
          height: 16,
          color: '#333333',
          layer: 'labels',
        },
        {
          type: 'TEXT',
          position: { x: 280, y: 100 },
          content: '卧室A 22㎡',
          height: 16,
          color: '#333333',
          layer: 'labels',
        },
        {
          type: 'TEXT',
          position: { x: 50, y: 300 },
          content: '厨房 18㎡',
          height: 16,
          color: '#333333',
          layer: 'labels',
        },
        {
          type: 'TEXT',
          position: { x: 280, y: 300 },
          content: '卧室B 20㎡',
          height: 16,
          color: '#333333',
          layer: 'labels',
        },
      ];

    case 'dxf_sample_3': // 电路原理图
      return [
        // 电源
        {
          type: 'RECT',
          min: { x: 0, y: 130 },
          max: { x: 60, y: 170 },
          color: '#FF0000',
          layer: 'power',
        },
        {
          type: 'TEXT',
          position: { x: 5, y: 195 },
          content: 'VCC 5V',
          height: 12,
          color: '#FF0000',
          layer: 'power',
        },
        // 电阻
        {
          type: 'RECT',
          min: { x: 120, y: 130 },
          max: { x: 160, y: 170 },
          color: '#0000FF',
          layer: 'components',
        },
        {
          type: 'TEXT',
          position: { x: 110, y: 195 },
          content: '10kΩ',
          height: 12,
          color: '#333333',
          layer: 'labels',
        },
        // 电容
        {
          type: 'RECT',
          min: { x: 240, y: 120 },
          max: { x: 280, y: 180 },
          color: '#0066CC',
          layer: 'components',
        },
        {
          type: 'TEXT',
          position: { x: 230, y: 200 },
          content: '100μF',
          height: 12,
          color: '#333333',
          layer: 'labels',
        },
        // 连接线
        {
          type: 'LINE',
          start: { x: 60, y: 150 },
          end: { x: 120, y: 150 },
          color: '#333333',
          layer: 'connections',
        },
        {
          type: 'LINE',
          start: { x: 160, y: 150 },
          end: { x: 240, y: 150 },
          color: '#333333',
          layer: 'connections',
        },
        {
          type: 'LINE',
          start: { x: 140, y: 100 },
          end: { x: 140, y: 130 },
          color: '#333333',
          layer: 'connections',
        },
        {
          type: 'LINE',
          start: { x: 140, y: 170 },
          end: { x: 140, y: 200 },
          color: '#333333',
          layer: 'connections',
        },
        // 接地
        {
          type: 'LINE',
          start: { x: 100, y: 250 },
          end: { x: 140, y: 250 },
          color: '#333333',
          layer: 'connections',
        },
        {
          type: 'TEXT',
          position: { x: 145, y: 255 },
          content: 'GND',
          height: 12,
          color: '#333333',
          layer: 'labels',
        },
        // 芯片
        {
          type: 'RECT',
          min: { x: 340, y: 80 },
          max: { x: 420, y: 220 },
          color: '#555555',
          layer: 'components',
        },
        {
          type: 'TEXT',
          position: { x: 345, y: 240 },
          content: 'STM32F103',
          height: 11,
          color: '#333333',
          layer: 'labels',
        },
        // 芯片引脚连接
        {
          type: 'LINE',
          start: { x: 280, y: 150 },
          end: { x: 340, y: 150 },
          color: '#333333',
          layer: 'connections',
        },
      ];

    default:
      return [
        {
          type: 'RECT',
          min: { x: 50, y: 50 },
          max: { x: 350, y: 250 },
          color: '#666666',
          layer: '0',
        },
        { type: 'CIRCLE', center: { x: 200, y: 150 }, radius: 80, color: '#FF6700', layer: '0' },
        {
          type: 'LINE',
          start: { x: 50, y: 50 },
          end: { x: 350, y: 250 },
          color: '#00AA00',
          layer: '0',
        },
        {
          type: 'TEXT',
          position: { x: 180, y: 300 },
          content: 'Default Drawing',
          height: 18,
          color: '#333333',
          layer: '0',
        },
      ];
  }
}

function generateLayers(hash: string): DxfLayer[] {
  switch (hash) {
    case 'dxf_sample_1':
      return [
        { name: '0', color: '#666666', visible: true, locked: false, entityCount: 1 },
        { name: 'holes', color: '#FF4500', visible: true, locked: false, entityCount: 5 },
        { name: 'ribs', color: '#00AA00', visible: true, locked: false, entityCount: 2 },
        { name: 'dimensions', color: '#333333', visible: true, locked: true, entityCount: 2 },
        { name: 'guide', color: '#CCCCCC', visible: false, locked: false, entityCount: 1 },
      ];
    case 'dxf_sample_2':
      return [
        { name: 'walls', color: '#333333', visible: true, locked: true, entityCount: 3 },
        { name: 'doors', color: '#00AAFF', visible: true, locked: false, entityCount: 3 },
        { name: 'windows', color: '#00BBFF', visible: true, locked: false, entityCount: 2 },
        { name: 'columns', color: '#888888', visible: true, locked: true, entityCount: 5 },
        { name: 'labels', color: '#333333', visible: true, locked: false, entityCount: 4 },
      ];
    case 'dxf_sample_3':
      return [
        { name: 'power', color: '#FF0000', visible: true, locked: true, entityCount: 2 },
        { name: 'components', color: '#0000FF', visible: true, locked: false, entityCount: 3 },
        { name: 'connections', color: '#333333', visible: true, locked: false, entityCount: 5 },
        { name: 'labels', color: '#333333', visible: true, locked: false, entityCount: 4 },
      ];
    default:
      return [{ name: '0', color: '#666666', visible: true, locked: false, entityCount: 4 }];
  }
}

// ───── Mock 响应生成函数 ─────

export const mockDxfResponse = {
  /** 健康检查 */
  health(): DxfHealthResponse {
    return {
      status: 'ok',
      version: '2.1.0-mock',
      storage_used_mb: 15.6,
    };
  },

  /** 文件列表 */
  listFiles(): DxfFile[] {
    return FILE_LIST;
  },

  /** 渲染数据（几何 + 图层） */
  getRenderData(hash: string): DxfRenderData {
    const file = FILE_LIST.find((f) => f.hash === hash) || FILE_LIST[0];
    const entities = generateEntities(hash);
    const layers = generateLayers(hash);

    // 计算边界
    let minX = Infinity,
      minY = Infinity,
      maxX = -Infinity,
      maxY = -Infinity;
    for (const entity of entities) {
      switch (entity.type) {
        case 'LINE':
          minX = Math.min(minX, entity.start.x, entity.end.x);
          minY = Math.min(minY, entity.start.y, entity.end.y);
          maxX = Math.max(maxX, entity.start.x, entity.end.x);
          maxY = Math.max(maxY, entity.start.y, entity.end.y);
          break;
        case 'CIRCLE':
          minX = Math.min(minX, entity.center.x - entity.radius);
          minY = Math.min(minY, entity.center.y - entity.radius);
          maxX = Math.max(maxX, entity.center.x + entity.radius);
          maxY = Math.max(maxY, entity.center.y + entity.radius);
          break;
        case 'RECT':
          minX = Math.min(minX, entity.min.x);
          minY = Math.min(minY, entity.min.y);
          maxX = Math.max(maxX, entity.max.x);
          maxY = Math.max(maxY, entity.max.y);
          break;
        case 'TEXT':
          minX = Math.min(minX, entity.position.x);
          minY = Math.min(minY, entity.position.y - entity.height);
          maxX = Math.max(maxX, entity.position.x + entity.content.length * entity.height * 0.6);
          maxY = Math.max(maxY, entity.position.y);
          break;
      }
    }

    return {
      file_id: file.id,
      file_name: file.name,
      entities,
      layers,
      bounds: {
        min_x: isFinite(minX) ? minX : 0,
        min_y: isFinite(minY) ? minY : 0,
        max_x: isFinite(maxX) ? maxX : 100,
        max_y: isFinite(maxY) ? maxY : 100,
      },
    };
  },
};
