"""Send notifications from the persisted queue, independently of MQTT ingestion."""
import json
from http.client import HTTPException
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def send_message(settings, message):
    request = Request(
        f"https://api.telegram.org/bot{settings['token']}/sendMessage",
        data=json.dumps({'chat_id': settings['chat_id'], 'text': message}).encode(),
        headers={'Content-Type': 'application/json'},
    )
    try:
        with urlopen(request, timeout=5) as response:
            return 'accepted' if json.load(response).get('ok') is True else 'failed'
    except HTTPError:
        return 'failed'
    except (OSError, HTTPException, ValueError, AttributeError):
        # Telegram may have accepted the request before the connection closed.
        return 'unknown'


def run_notifications(store, stop):
    store.mark_interrupted_notifications()
    while not stop.is_set():
        entry = store.claim_notification()
        if entry is None:
            stop.wait(0.5)
            continue
        status = send_message(store.cfg['telegram'], entry['message'])
        store.finish_notification(entry['event_id'], status)
