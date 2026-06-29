// 空状态组件
var EmptyStates = {
  graph: function(container) {
    container.innerHTML = '<div class="empty-state"><div class="empty-icon">🕸️</div><div class="empty-title">知识图谱为空</div><div class="empty-desc">上传文档后，系统会自动抽取实体和关系构建知识图谱。</div><button class="empty-btn" onclick="switchPanel(\'upload\')">📄 上传文档</button></div>';
  },
  wiki: function(container) {
    container.innerHTML = '<div class="empty-state"><div class="empty-icon">📚</div><div class="empty-title">Wiki 暂无内容</div><div class="empty-desc">上传文档后，系统会自动蒸馏生成 Wiki 知识页面。</div><button class="empty-btn" onclick="switchPanel(\'upload\')">📄 上传文档</button></div>';
  },
  search: function(container, query) {
    container.innerHTML = '<div class="empty-state"><div class="empty-icon">🔍</div><div class="empty-title">未找到相关内容</div><div class="empty-desc">没有找到与「' + (query||'') + '」匹配的内容，试试换个关键词？</div></div>';
  },
  files: function(container) {
    container.innerHTML = '<div class="empty-state"><div class="empty-icon">📂</div><div class="empty-title">暂无文件</div><div class="empty-desc">上传文档开始构建知识库。</div><button class="empty-btn" onclick="switchPanel(\'upload\')">📄 上传文档</button></div>';
  }
};
