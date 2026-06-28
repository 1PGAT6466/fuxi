// 骨架屏组件
var Skeleton = {
  show: function(container, count) {
    count = count || 3;
    var html = '';
    for (var i = 0; i < count; i++) {
      html += '<div class="skeleton-item"><div class="skeleton-line" style="width:' + (60 + Math.random()*40) + '%"></div><div class="skeleton-line short" style="width:' + (30 + Math.random()*30) + '%"></div></div>';
    }
    container.innerHTML = html;
  },
  hide: function(container) {
    var items = container.querySelectorAll('.skeleton-item');
    items.forEach(function(item) { item.remove(); });
  }
};
