// Cache strategy:
// - APP_SHELL (HTML, CSS, JS, icons, manifest): cache-first, versioned.
// - AUDIO (latest.mp3): stale-while-revalidate keyed by manifest date.
// - MANIFEST (latest.json): network-first with cache fallback.

const SHELL_CACHE = "stiritata-shell-v1";
const AUDIO_CACHE = "stiritata-audio-v1";

const SHELL_ASSETS = [
  "./",
  "index.html",
  "style.css",
  "app.js",
  "manifest.webmanifest",
  "icons/icon-192.png",
  "icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then((cache) => cache.addAll(SHELL_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(
        names
          .filter((n) => ![SHELL_CACHE, AUDIO_CACHE].includes(n))
          .map((n) => caches.delete(n))
      )
    )
  );
  self.clients.claim();
});

function isManifest(url) {
  return url.pathname.endsWith("/latest.json") || url.pathname.endsWith("latest.json");
}

function isAudio(url) {
  return url.pathname.endsWith(".mp3");
}

function isShell(url) {
  return SHELL_ASSETS.some((asset) => {
    if (asset === "./") return url.pathname.endsWith("/") || url.pathname.endsWith("/index.html");
    return url.pathname.endsWith(asset);
  });
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);

  if (isManifest(url)) {
    // Network-first for the manifest so we pick up new bulletins quickly.
    event.respondWith(
      fetch(req)
        .then((resp) => {
          const copy = resp.clone();
          caches.open(AUDIO_CACHE).then((c) => c.put(req, copy));
          return resp;
        })
        .catch(() => caches.match(req))
    );
    return;
  }

  if (isAudio(url)) {
    // Stale-while-revalidate: serve cache immediately, refresh in background.
    event.respondWith(
      caches.open(AUDIO_CACHE).then(async (cache) => {
        const cached = await cache.match(req, { ignoreSearch: true });
        const networkPromise = fetch(req)
          .then((resp) => {
            if (resp && resp.ok) cache.put(req, resp.clone());
            return resp;
          })
          .catch(() => cached);
        return cached || networkPromise;
      })
    );
    return;
  }

  if (isShell(url)) {
    event.respondWith(
      caches.match(req).then((cached) => cached || fetch(req))
    );
    return;
  }

  // Default: try network, fall back to cache.
  event.respondWith(fetch(req).catch(() => caches.match(req)));
});
