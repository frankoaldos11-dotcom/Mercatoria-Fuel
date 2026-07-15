// IMPORTANTE: bumpear CACHE_NAME (ej. v1 -> v2) en cada cambio de CSS o de
// tokens/*.json. Con cache-first para /static/*, si no se sube la version
// el navegador sigue sirviendo el CSS viejo desde cache indefinidamente
// (esto ya costo una sesion entera de diagnostico en Mercatoria Truck).
const CACHE_NAME = "mercatoria-fuel-v1";

const STATIC_ASSETS = [
  "/",
  "/static/css/admin.css",
  "/static/css/tokens.css",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
  "/static/manifest.json"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;

  // Never intercept non-GET or API/POST routes
  if (request.method !== "GET") return;

  const url = new URL(request.url);

  // Skip cross-origin requests (CDN, fonts, etc.)
  if (url.origin !== self.location.origin) return;

  // Skip todas las rutas autenticadas/dinamicas — siempre fetch fresco del servidor
  const BYPASS_PREFIXES = [
    "/adjuntos",
    "/choferes",
    "/clientes",
    "/conciliacion",
    "/configuracion",
    "/depositos",
    "/despachos",
    "/gasolineras",
    "/habilitaciones",
    "/mensajes",
    "/portal",
    "/puertos",
    "/recepciones",
    "/registro",
    "/reportes",
    "/tarjetas",
    "/tienda",
    "/transferencias",
    "/turno",
    "/unidades",
    "/usuarios",
    "/vehiculos",
    "/dashboard",
    "/login",
    "/logout",
    "/recuperar",
    "/qr",
  ];
  if (BYPASS_PREFIXES.some((p) => url.pathname.startsWith(p))) return;

  // For static assets: cache-first
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(request).then(
        (cached) => cached || fetch(request).then((response) => {
          if (response && response.status === 200) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          }
          return response;
        })
      )
    );
    return;
  }

  // For the homepage only: network-first, fall back to cache
  if (url.pathname === "/") {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          return response;
        })
        .catch(() => caches.match(request))
    );
  }
});
