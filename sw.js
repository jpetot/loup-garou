const VERSION = "loup-garou-v1";
const FICHIERS = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./css/pico.min.css",
  "./css/style.css",
  "./icons/icon.svg",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./js/app.js",
  "./js/aleatoire.js",
  "./js/composition.js",
  "./js/partie.js",
  "./js/roles.js",
  "./js/stockage.js",
  "./js/data/roles.js",
];

self.addEventListener("install", (evenement) => {
  evenement.waitUntil(caches.open(VERSION).then((cache) => cache.addAll(FICHIERS)));
  self.skipWaiting();
});

self.addEventListener("activate", (evenement) => {
  evenement.waitUntil(
    caches
      .keys()
      .then((cles) => Promise.all(cles.filter((c) => c !== VERSION).map((c) => caches.delete(c))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (evenement) => {
  if (evenement.request.method !== "GET") return;
  evenement.respondWith(
    fetch(evenement.request)
      .then((reponse) => {
        if (reponse.ok && new URL(evenement.request.url).origin === location.origin) {
          const copie = reponse.clone();
          caches.open(VERSION).then((cache) => cache.put(evenement.request, copie));
        }
        return reponse;
      })
      .catch(() =>
        caches.match(evenement.request, { ignoreSearch: true }).then((r) => r ?? caches.match("./")),
      ),
  );
});
