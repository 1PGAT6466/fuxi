# 伏羲前端 CSS 命名规范

## BEM 命名规范

采用 BEM (Block-Element-Modifier) 命名规范，确保样式可维护、无冲突。

### 基本格式

```
.block {}
.block__element {}
.block--modifier {}
.block__element--modifier {}
```

### 规则

1. **Block（块）**：独立的功能组件，可独立使用
   - 使用小写字母和连字符：`.card`, `.nav-item`, `.search-box`

2. **Element（元素）**：块的组成部分，不能独立使用
   - 使用双下划线连接：`.card__header`, `.card__body`, `.nav-item__icon`

3. **Modifier（修饰符）**：表示块或元素的状态、变体
   - 使用双连字符连接：`.card--primary`, `.btn--disabled`, `.nav-item--active`

### 命名示例

```css
/* Block */
.card {}

/* Element */
.card__header {}
.card__title {}
.card__body {}
.card__footer {}

/* Modifier */
.card--primary {}
.card--disabled {}
.card__title--large {}
```

## 现有组件对照表

### 1. 卡片组件 (Card)

| 原始选择器 | BEM 命名 |
|-----------|---------|
| `.card` | `.card` |
| `.card-header` | `.card__header` |
| `.card-header h3` | `.card__title` |
| `.card-body` | `.card__body` |
| `.card:hover` | `.card:hover` |

### 2. 按钮组件 (Button)

| 原始选择器 | BEM 命名 |
|-----------|---------|
| `.btn` | `.btn` |
| `.btn-orange` | `.btn--orange` |
| `.btn-primary` | `.btn--primary` |
| `.btn-ghost` | `.btn--ghost` |
| `.btn-sm` | `.btn--sm` |
| `.btn-icon` | `.btn--icon` |

### 3. 输入框组件 (Input)

| 原始选择器 | BEM 命名 |
|-----------|---------|
| `.input` | `.input` |
| `.search-bar` | `.search-bar` |
| `.search-bar .input` | `.search-bar__input` |

### 4. 导航组件 (Navigation)

| 原始选择器 | BEM 命名 |
|-----------|---------|
| `.nav-item` | `.nav-item` |
| `.nav-item.active` | `.nav-item--active` |
| `.nav-item svg` | `.nav-item__icon` |
| `.nav-item .badge` | `.nav-item__badge` |

### 5. 消息组件 (Message)

| 原始选择器 | BEM 命名 |
|-----------|---------|
| `.msg` | `.msg` |
| `.msg.user` | `.msg--user` |
| `.msg.ai` | `.msg--ai` |
| `.msg-avatar` | `.msg__avatar` |
| `.msg-bubble` | `.msg__bubble` |
| `.msg-sources` | `.msg__sources` |
| `.msg-trace` | `.msg__trace` |

### 6. 统计卡片 (Stats)

| 原始选择器 | BEM 命名 |
|-----------|---------|
| `.stat` | `.stat` |
| `.stat-icon` | `.stat__icon` |
| `.stat-value` | `.stat__value` |
| `.stat-label` | `.stat__label` |

### 7. 搜索结果 (Search Result)

| 原始选择器 | BEM 命名 |
|-----------|---------|
| `.result` | `.result` |
| `.result-title` | `.result__title` |
| `.result-text` | `.result__text` |
| `.result-meta` | `.result__meta` |

### 8. 侧边栏 (Sidebar)

| 原始选择器 | BEM 命名 |
|-----------|---------|
| `.sidebar` | `.sidebar` |
| `.sidebar-header` | `.sidebar__header` |
| `.sidebar-brand` | `.sidebar__brand` |
| `.sidebar-nav` | `.sidebar__nav` |
| `.sidebar-footer` | `.sidebar__footer` |

### 9. 文件管理 (File)

| 原始选择器 | BEM 命名 |
|-----------|---------|
| `.file-card` | `.file-card` |
| `.file-icon` | `.file-card__icon` |
| `.file-name` | `.file-card__name` |
| `.file-meta` | `.file-card__meta` |

### 10. 表格 (Table)

| 原始选择器 | BEM 命名 |
|-----------|---------|
| `.table-wrap` | `.table-wrap` |
| `table.data` | `.data-table` |
| `table.data th` | `.data-table__header` |
| `table.data td` | `.data-table__cell` |

## CSS 变量命名规范

使用有意义的变量名，按功能分组：

```css
/* 颜色 */
--color-primary: #FF6700;
--color-primary-light: #FF8533;
--color-primary-dark: #E55D00;
--color-background: #F5F5F5;
--color-surface: #FFFFFF;
--color-text-primary: #1F1F1F;
--color-text-secondary: #666666;
--color-text-tertiary: #999999;
--color-border: #E8E8E8;

/* 间距 */
--spacing-xs: 4px;
--spacing-sm: 8px;
--spacing-md: 16px;
--spacing-lg: 24px;
--spacing-xl: 32px;

/* 圆角 */
--radius-sm: 8px;
--radius-md: 12px;
--radius-lg: 16px;

/* 阴影 */
--shadow-sm: 0 2px 12px rgba(0,0,0,0.06);
--shadow-md: 0 4px 20px rgba(0,0,0,0.1);
--shadow-lg: 0 8px 40px rgba(0,0,0,0.12);
```

## 迁移策略

1. **渐进式迁移**：新代码必须使用 BEM 命名
2. **向后兼容**：旧选择器保留别名，逐步替换
3. **测试验证**：每次修改后检查页面样式
4. **文档更新**：修改后更新本文档

## 注意事项

- 避免使用 ID 选择器（`#id`），优先使用类选择器
- 避免超过 3 层嵌套的选择器
- 避免使用 `!important`
- 使用 CSS 变量管理主题和间距
