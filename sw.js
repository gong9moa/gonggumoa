/**
 * 공구모아 서비스워커 — 웹푸시 수신 담당
 *
 * 이 파일은 GitHub 저장소의 "맨 위 폴더"에 sw.js 라는 이름으로 올려야 해요.
 * (index.html 과 같은 위치. 하위 폴더에 두면 동작하지 않아요)
 *
 * 하는 일
 *  - 서버가 보낸 푸시를 받아 알림을 띄워요.
 *  - 알림을 누르면 구매 링크(또는 공구모아)로 이동시켜요.
 *
 * ⚠️ 혹시 이미 sw.js 파일이 있다면 이 내용으로 덮어쓰기 전에 알려주세요.
 *    기존 파일에 오프라인 캐시 같은 다른 기능이 들어있으면 합쳐야 해요.
 */

// 새 버전을 올리면 기다리지 않고 바로 적용
self.addEventListener('install', function (event) {
  self.skipWaiting();
});

self.addEventListener('activate', function (event) {
  event.waitUntil(self.clients.claim());
});

// ── 푸시 수신 ──
self.addEventListener('push', function (event) {
  var data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    // JSON이 아니면 본문을 그대로 메시지로
    data = { title: '공구모아', body: event.data ? event.data.text() : '' };
  }

  var title = data.title || '공구모아';
  var options = {
    body: data.body || '',
    icon: '/icon-192.png',
    badge: '/favicon-32.png',
    lang: 'ko',
    requireInteraction: false,
    data: { url: data.url || 'https://gonggumoa.com/' },
    // 같은 공구 알림이 여러 번 오면 쌓이지 않고 최신 것으로 덮어써요
    tag: data.url || 'gonggumoa',
    renotify: true
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

// ── 알림 클릭 ──
self.addEventListener('notificationclick', function (event) {
  event.notification.close();
  var target = (event.notification.data && event.notification.data.url) || 'https://gonggumoa.com/';

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (list) {
      // 이미 그 페이지가 열려 있으면 그 창을 앞으로
      for (var i = 0; i < list.length; i++) {
        if (list[i].url === target && 'focus' in list[i]) return list[i].focus();
      }
      if (self.clients.openWindow) return self.clients.openWindow(target);
    })
  );
});
