const CACHE_NAME = 'dametab-cache-v2'; // v2: fuerza actualización del cache viejo (que tenía rutas rotas)
const urlsToCache = [
  './',
  './index.html',
  './style.css',
  './app.js',
  './manifest.json'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        // Cacheamos cada recurso por separado: si uno falla, no se cae toda la instalación
        // (esto era lo que rompía el SW antes, por los íconos que no existían)
        return Promise.all(
          urlsToCache.map(url =>
            cache.add(url).catch(err => {
              console.warn('No se pudo cachear:', url, err);
            })
          )
        );
      })
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        if (response) {
          return response;
        }
        return fetch(event.request);
      })
  );
});

self.addEventListener('activate', event => {
  const cacheWhitelist = [CACHE_NAME];
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheWhitelist.indexOf(cacheName) === -1) {
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});
