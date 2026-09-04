"use strict";

function safeNotificationUrl(candidate) {
  try {
    const url = new URL(String(candidate || "./"), self.location.href);
    return url.origin === self.location.origin ? url.href : new URL("./", self.location.href).href;
  } catch (_error) {
    return new URL("./", self.location.href).href;
  }
}

self.addEventListener("push", (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch (_error) {
    payload = { body: "A new trading alert is available." };
  }

  const title = String(payload.title || "Candlestick Alert").slice(0, 120);
  const options = {
    body: String(payload.body || "Open the dashboard for details.").slice(0, 240),
    tag: String(payload.tag || "candlestick-alert").slice(0, 128),
    renotify: true,
    data: { url: safeNotificationUrl(payload.url) },
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetUrl = safeNotificationUrl(event.notification.data?.url);
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if (new URL(client.url).origin === self.location.origin) {
          return client.navigate(targetUrl).then(() => client.focus());
        }
      }
      return self.clients.openWindow(targetUrl);
    })
  );
});
