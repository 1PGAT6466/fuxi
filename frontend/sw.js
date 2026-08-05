/**
 * 伏羲 v2.1 — Service Worker（离线模式增强版）
 *
 * 功能：
 * - 静态资源缓存（Cache-first）
 * - API 请求离线降级（Network-first + 离线兜底）
 * - 离线操作队列支持（通过 MessageChannel 与主线程通信）
 * - 接收 Web Push 推送并在离线时显示通知
 * - 通知点击打开伏羲应用
 */

// ═══════════════════════════════════════════
// 缓存配置
// ═══════════════════════════════════════════

const CACHE_NAME = 'fuxi-v2.1-cache-v2';
const API_CACHE_NAME = 'fuxi-v2.1-api-cache-v1';
const RUNTIME_CACHE_NAME = 'fuxi-v2.1-runtime-v1';

const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/favicon.ico',
];

// 需要缓存的静态资源扩展名
const CACHEABLE_EXTENSIONS = [
  '.js', '.css', '.woff', '.woff2', '.ttf', '.eot',
  '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.webp',
  '.json', '.map',
];

// 需要 Network-first 的 API 模式
const API_PATTERNS = ['/api/'];

// ═══════════════════════════════════════════
// Install：预缓存静态资源
// ═══════════════════════════════════════════

self.addEventListener('install', (event) => {
  console.log('[Fuxi SW] Installing...');
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[Fuxi SW] Caching static assets');
      return cache.addAll(STATIC_ASSETS).catch((err) => {
        console.warn('[Fuxi SW] Cache addAll partial failure', err);
      });
    }),
  );
  // 立即激活
  self.skipWaiting();
});

// ═══════════════════════════════════════════
// Activate：清理旧缓存
// ═══════════════════════════════════════════

self.addEventListener('activate', (event) => {
  console.log('[Fuxi SW] Activating...');
  const VALID_CACHES = [CACHE_NAME, API_CACHE_NAME, RUNTIME_CACHE_NAME];
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => !VALID_CACHES.includes(name))
          .map((name) => {
            console.log('[Fuxi SW] Deleting old cache:', name);
            return caches.delete(name);
          }),
      );
    }),
  );
  // 立即接管所有页面
  self.clients.claim();
});

// ═══════════════════════════════════════════
// 工具函数
// ═══════════════════════════════════════════

/** 检查请求是否为 API 请求 */
function isApiRequest(url) {
  return API_PATTERNS.some((pattern) => url.includes(pattern));
}

/** 检查请求是否可缓存 */
function isCacheableAsset(url) {
  return CACHEABLE_EXTENSIONS.some((ext) => url.toLowerCase().endsWith(ext));
}

/** 生成 API 缓存的 key */
function getApiCacheKey(request) {
  return request.url + (request.headers.get('Authorization') || '');
}

/** 通知主线程离线状态变更 */
async function notifyClients(message) {
  const clients = await self.clients.matchAll({ type: 'window' });
  clients.forEach((client) => {
    client.postMessage(message);
  });
}

// ═══════════════════════════════════════════
// Fetch：智能缓存策略
// ═══════════════════════════════════════════

self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = request.url;

  // 跳过非 GET 请求
  if (request.method !== 'GET') {
    // 对于离线操作（POST/PUT/DELETE），通知主线程加入离线队列
    if (request.method !== 'GET' && isApiRequest(url)) {
      // 暂不在此处拦截，由主线程 OfflineService 处理
    }
    return;
  }

  // 跳过 websocket
  if (url.startsWith('ws')) return;

  // 跳过 chrome-extension
  if (url.startsWith('chrome-extension://')) return;

  // ========== 策略 1: API 请求 → Network-first ==========
  if (isApiRequest(url)) {
    event.respondWith(networkFirstWithApiFallback(request));
    return;
  }

  // ========== 策略 2: 静态资源 → Cache-first ==========
  if (isCacheableAsset(url)) {
    event.respondWith(cacheFirstWithNetworkUpdate(request));
    return;
  }

  // ========== 策略 3: HTML 导航 → Network-first with offline fallback ==========
  if (request.mode === 'navigate') {
    event.respondWith(networkFirstWithHtmlFallback(request));
    return;
  }

  // ========== 策略 4: 其他 → Stale-while-revalidate ==========
  event.respondWith(staleWhileRevalidate(request));
});

/**
 * Cache-first 策略（静态资源）
 * 优先返回缓存，后台更新
 */
async function cacheFirstWithNetworkUpdate(request) {
  const cache = await caches.open(CACHE_NAME);
  const cached = await cache.match(request);

  // 后台更新缓存
  const fetchPromise = fetch(request)
    .then((response) => {
      if (response && response.status === 200) {
        cache.put(request, response.clone());
      }
      return response;
    })
    .catch(() => null);

  if (cached) {
    // 不等待后台更新
    return cached;
  }

  // 缓存未命中，等网络响应
  try {
    const networkResponse = await fetchPromise;
    return networkResponse || new Response('', { status: 408 });
  } catch {
    return new Response('', { status: 408, statusText: 'Offline - resource not cached' });
  }
}

/**
 * Network-first 策略（API 请求）
 * 优先请求网络，失败时降级到缓存
 */
async function networkFirstWithApiFallback(request) {
  try {
    const response = await fetch(request);

    if (response && response.status === 200) {
      // 缓存成功的 API 响应
      const cache = await caches.open(API_CACHE_NAME);
      cache.put(getApiCacheKey(request), response.clone());
    }

    return response;
  } catch (error) {
    // 网络失败，尝试从缓存读取
    console.log('[Fuxi SW] API 离线降级:', request.url);

    const cache = await caches.open(API_CACHE_NAME);
    const cached = await cache.match(getApiCacheKey(request));

    if (cached) {
      // 通知主线程：API 请求已降级
      notifyClients({
        type: 'API_FALLBACK',
        url: request.url,
        timestamp: Date.now(),
      }).catch(() => {});

      // 返回缓存数据，添加自定义 header 标记
      const headers = new Headers(cached.headers);
      headers.set('X-Offline-Cache', 'true');
      headers.set('X-Offline-Cache-Time', cached.headers.get('date') || '');

      return new Response(cached.body, {
        status: cached.status,
        statusText: cached.statusText,
        headers: headers,
      });
    }

    // 没有缓存，返回离线错误
    return new Response(
      JSON.stringify({
        status: 'error',
        message: '当前离线，无法获取数据',
        code: 'OFFLINE',
      }),
      {
        status: 503,
        statusText: 'Service Unavailable - Offline',
        headers: { 'Content-Type': 'application/json' },
      },
    );
  }
}

/**
 * Network-first 策略（HTML 导航）
 * 用离线页面兜底
 */
async function networkFirstWithHtmlFallback(request) {
  try {
    const response = await fetch(request);

    if (response && response.status === 200) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }

    return response;
  } catch {
    // 返回缓存的 index.html
    const cache = await caches.open(CACHE_NAME);
    const cached = await cache.match(request);
    return cached || caches.match('/index.html');
  }
}

/**
 * Stale-while-revalidate 策略
 * 立即返回缓存，后台更新
 */
async function staleWhileRevalidate(request) {
  const cache = await caches.open(RUNTIME_CACHE_NAME);
  const cached = await cache.match(request);

  const fetchPromise = fetch(request)
    .then((response) => {
      if (response && response.status === 200) {
        cache.put(request, response.clone());
      }
      return response;
    })
    .catch(() => null);

  return cached || (await fetchPromise) || new Response('', { status: 408 });
}

// ═══════════════════════════════════════════
// Message：与主线程通信
// ═══════════════════════════════════════════

self.addEventListener('message', (event) => {
  const { type, payload } = event.data || {};

  switch (type) {
    case 'SKIP_WAITING':
      self.skipWaiting();
      break;

    case 'CLEAR_API_CACHE':
      event.waitUntil(
        caches.delete(API_CACHE_NAME).then(() => {
          console.log('[Fuxi SW] API 缓存已清除');
          notifyClients({ type: 'API_CACHE_CLEARED' });
        }),
      );
      break;

    case 'CLEAR_ALL_CACHE':
      event.waitUntil(
        Promise.all([
          caches.delete(CACHE_NAME),
          caches.delete(API_CACHE_NAME),
          caches.delete(RUNTIME_CACHE_NAME),
        ]).then(() => {
          console.log('[Fuxi SW] 所有缓存已清除');
          notifyClients({ type: 'ALL_CACHE_CLEARED' });
        }),
      );
      break;

    case 'UPDATE_CACHE':
      if (payload && payload.url) {
        event.waitUntil(
          fetch(payload.url)
            .then((response) => {
              return caches.open(CACHE_NAME).then((cache) => {
                return cache.put(payload.url, response);
              });
            })
            .catch((err) => {
              console.warn('[Fuxi SW] 缓存更新失败', payload.url, err);
            }),
        );
      }
      break;

    default:
      console.log('[Fuxi SW] 未知消息类型:', type);
  }
});

// ═══════════════════════════════════════════
// Push：接收 Web Push 通知
// ═══════════════════════════════════════════

self.addEventListener('push', (event) => {
  console.log('[Fuxi SW] Push received:', event);

  let title = '伏羲';
  let options = {
    body: '您有一条新通知',
    icon: '/favicon.ico',
    badge: '/favicon.ico',
    tag: 'fuxi-notification',
    data: {
      url: '/',
    },
    requireInteraction: false,
    vibrate: [200, 100, 200],
    actions: [
      {
        action: 'open',
        title: '查看详情',
      },
      {
        action: 'close',
        title: '关闭',
      },
    ],
  };

  if (event.data) {
    try {
      const payload = event.data.json();
      title = payload.title || title;
      options.body = payload.body || options.body;
      if (payload.icon) options.icon = payload.icon;
      if (payload.badge) options.badge = payload.badge;
      if (payload.tag) options.tag = payload.tag;
      if (payload.data) {
        options.data = { ...options.data, ...payload.data };
      }
      if (payload.requireInteraction !== undefined) {
        options.requireInteraction = payload.requireInteraction;
      }
      if (payload.actions) {
        options.actions = payload.actions;
      }
    } catch {
      // 非 JSON 格式，当作纯文本 body
      options.body = event.data.text();
    }
  }

  event.waitUntil(
    self.registration.showNotification(title, options),
  );
});

// ═══════════════════════════════════════════
// Notification Click：点击通知打开应用
// ═══════════════════════════════════════════

self.addEventListener('notificationclick', (event) => {
  console.log('[Fuxi SW] Notification clicked:', event);

  event.notification.close();

  const urlToOpen = event.notification.data?.url || '/';

  if (event.action === 'close') {
    return;
  }

  event.waitUntil(
    self.clients
      .matchAll({ type: 'window', includeUncontrolled: true })
      .then((clientList) => {
        // 查找是否已有打开的窗口
        for (const client of clientList) {
          if (client.url.includes(self.location.origin) && 'focus' in client) {
            return client.focus();
          }
        }
        // 没有窗口则打开新窗口
        if (self.clients.openWindow) {
          return self.clients.openWindow(urlToOpen);
        }
      }),
  );
});

// ═══════════════════════════════════════════
// Push Subscription Change：订阅变更处理
// ═══════════════════════════════════════════

self.addEventListener('pushsubscriptionchange', (event) => {
  console.log('[Fuxi SW] Push subscription changed');

  // 重新订阅逻辑由主线程处理
  event.waitUntil(
    self.registration.pushManager
      .subscribe({
        userVisibleOnly: true,
      })
      .then((newSubscription) => {
        console.log('[Fuxi SW] Re-subscribed after change');
        // 通知主线程更新订阅
        self.clients.matchAll({ type: 'window' }).then((clients) => {
          clients.forEach((client) => {
            client.postMessage({
              type: 'PUSH_SUBSCRIPTION_CHANGE',
              subscription: newSubscription,
            });
          });
        });
      })
      .catch((err) => {
        console.error('[Fuxi SW] Re-subscription failed', err);
      }),
  );
});
