"""Find private Telegram chats that sent /start to the project's bot."""
import json
import os
import re
import sys
from urllib.request import Request, urlopen


def main():
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
    if not re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]+', token):
        sys.exit('Set TELEGRAM_BOT_TOKEN in this PowerShell session first.')
    request = Request(
        f'https://api.telegram.org/bot{token}/getUpdates',
        data=b'{"limit":100,"allowed_updates":["message"]}',
        headers={'Content-Type': 'application/json'},
    )
    try:
        with urlopen(request, timeout=10) as response:
            result = json.load(response)
        if result.get('ok') is not True:
            sys.exit('Telegram rejected the request. Check the token and bot setup.')
        chats = set()
        for item in result['result']:
            message = item.get('message', {})
            chat = message.get('chat', {})
            command = message.get('text', '').split()
            if chat.get('type') == 'private' and command and command[0] == '/start':
                chats.add(chat['id'])
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        sys.exit('Could not read Telegram updates. Check Internet access, the token, and bot setup.')
    if not chats:
        sys.exit('No private /start messages found. Open your bot on the phone, tap Start and retry.')
    print('Private chat ID(s) found. Enter the ID of the phone account you intend to notify:')
    for chat_id in sorted(chats):
        print(chat_id)


if __name__ == '__main__':
    main()
