import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
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

    def request(self, method, url, body=None, headers=None, *, server=None):
        conn = HTTPConnection('127.0.0.1', (server or self.server).server_port, timeout=4)
        try:
            conn.request(method, url, body, headers or {})
            response = conn.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            conn.close()

    @contextmanager
    def account_server(self, gate):
        server = create_server(self.store, {}, port=0, gate=gate)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_requires_session_before_dashboard_and_api(self):
        code, headers, _ = self.request('GET', '/')
        self.assertEqual((code, headers['Location']), (303, '/login'))
        self.assertEqual(self.request('GET', '/api/devices')[0], 401)
        self.assertEqual(self.request('GET', '/api/camera/clips')[0], 401)
        self.assertEqual(self.request('GET', '/media/gmdcsa24/subject-1-adl-08.mp4')[0], 401)
        self.assertEqual(self.request('POST', '/api/alerts/1/ack')[0], 401)
        self.assertIn(b'Sign in', self.request('GET', '/login')[2])
        self.assertNotIn(b'/signup', self.request('GET', '/login')[2])
        self.assertEqual(self.request('GET', '/signup')[0], 404)

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

    def test_signup_only_persists_account_with_secure_session(self):
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        username, password = 'Lovely_Home', 'test-account-password'
        with tempfile.TemporaryDirectory() as temp:
            account = Path(temp) / 'auth.local.json'
            gate = AccessGate(account, ROOT / 'dashboard', secure=True, allow_signup=True)
            with self.account_server(gate) as server:
                self.assertIn(b'/signup', self.request('GET', '/login', server=server)[2])
                self.assertIn(b'Create an account', self.request('GET', '/signup', server=server)[2])
                fields = {'username': username, 'password': password, 'confirm': 'wrong password'}
                status, _, body = self.request('POST', '/signup', urlencode(fields), headers, server=server)
                self.assertEqual(status, 400)
                self.assertIn(b'do not match', body)
                self.assertNotIn(password.encode(), body)
                fields['confirm'] = password
                status, _, _ = self.request('POST', '/signup', urlencode(fields),
                                            {**headers, 'Origin': 'https://other.invalid'}, server=server)
                self.assertEqual(status, 403)
                status, result, _ = self.request('POST', '/signup', urlencode(fields), headers, server=server)
                self.assertEqual((status, result['Location']), (303, '/'))
                session = result['Set-Cookie']
                self.assertTrue(session.startswith('__Host-home_iot_session='))
                for flag in ('Secure', 'HttpOnly', 'SameSite=Strict'):
                    self.assertIn(flag, session)
                cookie = {'Cookie': session.split(';')[0]}
                self.assertEqual(self.request('GET', '/api/devices', headers=cookie, server=server)[0], 200)
                self.assertEqual(self.request('POST', '/logout', headers=cookie, server=server)[0], 303)
                self.assertEqual(self.request('GET', '/api/devices', headers=cookie, server=server)[0], 401)
            self.assertNotIn(password.encode(), gate.accounts_file.read_bytes())
            with self.account_server(AccessGate(account, ROOT / 'dashboard', secure=True)) as server:
                self.assertEqual(self.request('GET', '/signup', server=server)[0], 404)
                login = urlencode({'username': username.lower(), 'password': password})
                self.assertEqual(self.request('POST', '/login', login, headers, server=server)[0], 303)

    def test_duplicate_concurrent_signup_and_rate_limit(self):
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        with tempfile.TemporaryDirectory() as temp:
            account = Path(temp) / 'auth.local.json'
            password = 'test-duplicate-password'
            write_account(account, 'demo', password)
            gate = AccessGate(account, ROOT / 'dashboard', allow_signup=True)
            with self.account_server(gate) as server:
                def register(username):
                    fields = {'username': username, 'password': password, 'confirm': password}
                    return self.request('POST', '/signup', urlencode(fields), headers, server=server)[0]
                with ThreadPoolExecutor(max_workers=2) as requests:
                    self.assertEqual(sorted(requests.map(register, ('new-user', 'New-User'))), [303, 409])
                self.assertEqual([register('DEMO') for _ in range(4)], [409] * 4)
                self.assertEqual(register('another-user'), 429)
