/* אוצר שיעורי ר' יואל — Service Worker (Instant Repeat Loads & Chunk Caching) */
const BUILD_VERSION = "974e64cf2f";
const CACHE_NAME = `otzar-rebyoel-${BUILD_VERSION}`;

self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) =>
      cache.addAll([
        "./",
        "./index.html",
        "./icon.svg",
        "./manifest.webmanifest",
      ]).catch(() => {})
    )
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k.startsWith("otzar-rebyoel-") && k !== CACHE_NAME)
          .map((k) => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  // HTML navigations (including ?cat=... / ?shiur=...): Network-First so deploys apply immediately
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (res && res.ok) {
            const copy = res.clone();
            caches.open(CACHE_NAME).then((c) => c.put("./index.html", copy));
          }
          return res;
        })
        .catch(() => caches.match("./index.html").then((c) => c || caches.match("./")))
    );
    return;
  }

  // Versioned JS/CSS/chunks & static assets: Cache-First with background refresh if unversioned
  const isVersionedChunk = url.search.includes(`v=${BUILD_VERSION}`) || url.pathname.includes("/data/chunks/");
  if (isVersionedChunk) {
    event.respondWith(
      caches.match(req).then((cached) => {
        if (cached) return cached;
        return fetch(req).then((res) => {
          if (res && res.ok) {
            const copy = res.clone();
            caches.open(CACHE_NAME).then((c) => c.put(req, copy));
          }
          return res;
        });
      })
    );
    return;
  }

  event.respondWith(
    caches.match(req).then((cached) => {
      const fetchPromise = fetch(req).then((res) => {
        if (res && res.ok) {
          const copy = res.clone();
          caches.open(CACHE_NAME).then((c) => c.put(req, copy));
        }
        return res;
      }).catch(() => cached);
      return cached || fetchPromise;
    })
  );
});
