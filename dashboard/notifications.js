// The backend holds the recipient and bot credentials. The browser only shows delivery status.
'use strict';
(() => {
  const mode = document.getElementById('telegram-mode');
  const detail = document.getElementById('telegram-detail');
  const list = document.getElementById('telegram-events');
  const modes = {
    preview: ['Preview only', 'Gas and offline events appear here. No messages leave this demo.'],
    live: ['Telegram enabled', 'Messages go to the private Telegram chat configured on the backend.'],
    off: ['Off', 'Notification recording and sending are off.']
  };
  const statuses = {
    preview: 'Preview · not sent', queued: 'Queued', sending: 'Sending',
    accepted: 'Accepted by Telegram', failed: 'Telegram rejected the request',
    unknown: 'Delivery unconfirmed', expired: 'Expired', skipped: 'Simulated send skipped'
  };

  async function refreshNotifications() {
    try {
      const response = await fetch('/api/notifications', {signal: AbortSignal.timeout(4000)});
      if (!response.ok) throw Error('Notification request failed');
      const data = await response.json();
      [mode.textContent, detail.textContent] = modes[data.mode];
      const rows = data.items.slice(0, 4).map(item => {
        const row = document.createElement('li');
        const badge = document.createElement('strong');
        const message = document.createElement('p');
        badge.textContent = statuses[item.status] || item.status;
        badge.dataset.status = item.status;
        message.textContent = item.message;
        row.append(badge, message);
        return row;
      });
      if (!rows.length) {
        const empty = document.createElement('li');
        empty.textContent = 'Waiting for an alert or a device outage.';
        rows.push(empty);
      }
      list.replaceChildren(...rows);
    } catch {
      mode.textContent = 'Connection unavailable';
      detail.textContent = 'The last notification list may be out of date.';
    } finally {
      setTimeout(refreshNotifications, 2000);
    }
  }
  refreshNotifications();
})();
