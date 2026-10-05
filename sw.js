const C = "jam-v1", SHELL = ["./", "index.html", "app.css", "app.js"];
self.addEventListener("install", e => e.waitUntil(caches.open(C).then(c => c.addAll(SHELL))));
self.addEventListener("fetch", e => {
  // データは network-first(常に最新)、失敗時のみキャッシュ
  e.respondWith(fetch(e.request).then(r => { const k = r.clone(); caches.open(C).then(c => c.put(e.request, k)); return r; })
    .catch(() => caches.match(e.request)));
});
