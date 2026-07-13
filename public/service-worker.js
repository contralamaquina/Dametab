// Service worker mínimo — solo lo necesario para que el navegador
// considere la app "instalable". No hace caché agresivo porque esta
// app depende de conexión en vivo (micrófono + APIs), no tiene sentido
// funcionar offline.

self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  self.clients.claim();
});

// Passthrough simple: deja pasar todas las peticiones normalmente.
self.addEventListener("fetch", (event) => {
  event.respondWith(fetch(event.request));
});
