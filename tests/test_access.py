import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path
from urllib.parse import urlencode

from backend.access import AccessGate
from backend.app import create_server
from backend.store import Store
from common.config import ROOT, load_config
from tools.set_demo_login import write_account


class LoginTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        root = Path(cls.temp.name)
        account = root / 'auth.local.json'
        write_account(account, 'demo', 'test-password-12345')
        cls.store = Store(root / 'demo.db', load_config())
        cls.server = create_server(cls.store, {}, port=0, gate=AccessGate(account, ROOT / 'dashboard'))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.store.close()
        cls.temp.cleanup()

    def request(self, method, url, body=None, headers=None):
        conn = HTTPConnection('127.0.0.1', self.server.server_port, timeout=4)
        try:
            conn.request(method, url, body, headers or {})
            response = conn.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            conn.close()

    def test_requires_session_before_dashboard_and_api(self):
        code, headers, _ = self.request('GET', '/')
        self.assertEqual((code, headers['Location']), (303, '/login'))
        self.assertEqual(self.request('GET', '/api/devices')[0], 401)
        self.assertEqual(self.request('POST', '/api/alerts/1/ack')[0], 401)
        self.assertIn(b'Sign in', self.request('GET', '/login')[2])

    def test_wrong_password_sign_in_and_sign_out(self):
        fields = {'username': 'demo', 'password': 'wrong'}
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        self.assertEqual(self.request('POST', '/login', urlencode(fields), headers)[0], 401)
        fields['password'] = 'test-password-12345'
        status, response, _ = self.request('POST', '/login', urlencode(fields), headers)
        self.assertEqual((status, response['Location']), (303, '/'))
        self.assertIn('HttpOnly', response['Set-Cookie'])
        cookie = {'Cookie': response['Set-Cookie'].split(';')[0]}
        self.assertEqual(self.request('GET', '/api/devices', headers=cookie)[0], 200)
        self.assertIn(b'id="logout-form" method=', self.request('GET', '/', headers=cookie)[2])
        self.assertEqual(self.request('POST', '/logout', headers={**cookie, 'Origin': 'https://other.invalid'})[0], 403)
        self.assertEqual(self.request('POST', '/logout', headers=cookie)[0], 303)
        self.assertEqual(self.request('GET', '/api/devices', headers=cookie)[0], 401)
