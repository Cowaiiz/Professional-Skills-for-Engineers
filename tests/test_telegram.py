import json
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from backend.telegram import send_message


class TelegramTransportTests(unittest.TestCase):
    def test_mocked_telegram_acceptance_and_failure(self):
        settings = {'token': '123:test', 'chat_id': '12345'}
        with patch('backend.telegram.urlopen') as open_url:
            response = MagicMock()
            response.read.return_value = '{"ok": true}'
            open_url.return_value.__enter__.return_value = response
            self.assertEqual(send_message(settings, 'Gas high'), 'accepted')
            request = open_url.call_args.args[0]
            self.assertEqual(request.full_url, 'https://api.telegram.org/bot123:test/sendMessage')
            self.assertEqual(json.loads(request.data), {'chat_id': '12345', 'text': 'Gas high'})
            open_url.side_effect = HTTPError(request.full_url, 400, 'Bad Request', {}, None)
            self.assertEqual(send_message(settings, 'Gas high'), 'failed')
            open_url.side_effect = TimeoutError()
            self.assertEqual(send_message(settings, 'Gas high'), 'unknown')
