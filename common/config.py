import copy
import hashlib
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load_config(path=None):
    cfg = json.loads((ROOT / 'config.example.json').read_text(encoding='utf-8'))
    local = Path(path) if path else ROOT / 'config.local.json'
    if local.exists():
        override = json.loads(local.read_text(encoding='utf-8-sig'))
        for key, value in override.items():
            if isinstance(value, dict) and key in cfg:
                cfg[key].update(value)
            else:
                cfg[key] = value
    for field in ('host', 'username', 'password'):
        if 'MQTT_' + field.upper() in os.environ:
            cfg['mqtt'][field] = os.environ['MQTT_' + field.upper()]
    if 'MQTT_PORT' in os.environ:
        cfg['mqtt']['port'] = int(os.environ['MQTT_PORT'])
    mode = os.environ.get('TELEGRAM_MODE', 'preview').strip().lower()
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
    if mode not in ('off', 'preview', 'live'):
        raise ValueError('TELEGRAM_MODE must be off, preview or live.')
    if mode == 'live' and not (re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]+', token)
                               and re.fullmatch(r'[1-9][0-9]{0,18}', chat_id)):
        raise ValueError('Live Telegram requires a valid bot token and a private chat ID.')
    cfg['telegram'] = {
        'mode': mode, 'token': token, 'chat_id': chat_id,
        'allow_simulated': os.environ.get('TELEGRAM_ALLOW_SIMULATED') == '1',
        'recipient_key': hashlib.sha256((token + '/' + chat_id).encode()).hexdigest() if mode == 'live' else None,
    }
    rules = cfg['rules']
    for stem in ('temperature', 'gas'):
        if not rules[stem + '_clear'] < rules[stem + '_high']:
            raise ValueError(stem + ' clear threshold must be lower than high threshold')
    for key in ('confirm_samples', 'digital_samples', 'offline_seconds', 'max_sample_gap'):
        if rules[key] <= 0:
            raise ValueError(key + ' must be positive')
    return copy.deepcopy(cfg)
