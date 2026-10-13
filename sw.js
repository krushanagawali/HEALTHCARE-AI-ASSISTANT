const CACHE_NAME = "stemi-app-cache-v1";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll([
        "/HEALTHCARE-AI-ASSISTANT/",
        "/HEALTHCARE-AI-ASSISTANT/index.html",
        "/HEALTHCARE-AI-ASSISTANT/day9_dashboard.html",
        "/HEALTHCARE-AI-ASSISTANT/day11_family_dashboard.html",
        "/HEALTHCARE-AI-ASSISTANT/day12_patient_dashboard.html"
      ]);
    })
  );
});

self.addEventListener("fetch", (event) => {
  event.respondWith(
    caches.match(event.request).then((response) => {
      return response || fetch(event.request);
    })
  );
});
