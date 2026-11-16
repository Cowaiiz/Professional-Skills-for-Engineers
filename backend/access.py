"""Password gate for a small Home IoT demo."""
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
import time
from collections import deque
from contextlib import closing
from html import escape
from http.cookies import CookieError, SimpleCookie
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


ROUNDS = 600_000
SESSION_SECONDS = 8 * 60 * 60
ACCOUNT_DB = 'accounts.local.db'
SIGNUP_ENV = 'HOME_IOT_ALLOW_SIGNUP'
USERNAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{2,31}')
FORM_TYPE = 'application/x-www-form-urlencoded'
CSP = ("default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self'; "
       "connect-src 'self'; media-src 'self' blob:; frame-ancestors 'none'; "
       "form-action 'self'; base-uri 'none'")


def password_hash(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, ROUNDS)


def local_auth_enabled(root):
    return (os.environ.get(SIGNUP_ENV) == '1' or (root / 'auth.local.json').is_file()
            or (root / ACCOUNT_DB).is_file())


class AccessGate:
    def __init__(self, account_file, dashboard, secure=False, allow_signup=False):
        account = Path(account_file)
        self.accounts_file = account.with_name(ACCOUNT_DB)
        self.allow_signup = allow_signup
        self.registered_accounts = allow_signup or self.accounts_file.exists()
        self.username = ''
        self.salt = secrets.token_bytes(16)
        self.digest = secrets.token_bytes(32)
        if account.exists() or not self.registered_accounts:
            settings = json.loads(account.read_text(encoding='utf-8'))
            self.username = settings['username']
            self.salt = bytes.fromhex(settings['salt'])
            self.digest = bytes.fromhex(settings['digest'])
            if not self.username or len(self.salt) != 16 or len(self.digest) != 32:
                raise ValueError('Invalid demo login configuration')
        if self.registered_accounts:
            with closing(sqlite3.connect(self.accounts_file)) as db, db:
                db.execute('CREATE TABLE IF NOT EXISTS accounts ('
                           'username TEXT PRIMARY KEY, salt BLOB NOT NULL, digest BLOB NOT NULL)')
        self.secure = secure
        self.cookie_name = '__Host-home_iot_session' if secure else 'home_iot_session'
        self.dashboard = Path(dashboard)
        self.sessions = {}
        self.attempts = {'login': deque(), 'signup': deque()}
        self.lock = threading.Lock()
        self.hash_slots = threading.BoundedSemaphore(4)

    def token(self, handler):
        raw = handler.headers.get('Cookie', '')
        if len(raw) > 4096:
            return ''
        try:
            cookie = SimpleCookie(raw).get(self.cookie_name)
        except CookieError:
            return ''
        return cookie.value if cookie else ''

    def signed_in(self, handler):
        with self.lock:
            return self.sessions.get(self.token(handler), 0) > time.monotonic()

    def cookie_header(self, token, age):
        secure_flag = '; Secure' if self.secure else ''
        return (f'{self.cookie_name}={token}; Path=/; Max-Age={age}; '
                f'HttpOnly; SameSite=Strict{secure_flag}')

    def send(self, handler, status, body=b'', kind='text/html; charset=utf-8', headers=()):
        handler.send_response(status)
        handler.send_header('Content-Type', kind)
        handler.send_header('Content-Length', str(len(body)))
        handler.send_header('Cache-Control', 'no-store')
        handler.send_header('Content-Security-Policy', CSP)
        handler.send_header('X-Content-Type-Options', 'nosniff')
        for name, value in headers:
            handler.send_header(name, value)
        handler.end_headers()
        if handler.command != 'HEAD':
            try:
                handler.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def redirect(self, handler, location, cookie=None):
        headers = [('Location', location)]
        if cookie is not None:
            headers.append(('Set-Cookie', cookie))
        self.send(handler, 303, headers=headers)

    def auth_page(self, handler, page_name, status=200, message=''):
        page = (self.dashboard / f'{page_name}.html').read_bytes()
        page = page.replace(b'<!-- auth-message -->', escape(message).encode('utf-8'))
        if page_name == 'login' and self.allow_signup:
            page = page.replace(b'<!-- signup-link -->',
                                b'<p class="auth-link">New here? <a href="/signup">Create an account</a></p>')
        self.send(handler, status, page)

    def valid_origin(self, handler):
        origin = handler.headers.get('Origin')
        if handler.headers.get('Sec-Fetch-Site') == 'cross-site':
            return False
        try:
            return not origin or urlsplit(origin).netloc == handler.headers.get('Host')
        except ValueError:
            return False

    def read_form(self, handler, fields):
        kind = handler.headers.get('Content-Type', '').split(';', 1)[0]
        length = int(handler.headers.get('Content-Length', '0'))
        if kind != FORM_TYPE or not 0 < length <= 8192:
            raise ValueError
        data = parse_qs(handler.rfile.read(length).decode('utf-8'), max_num_fields=len(fields))
        if any(len(data.get(field, [])) != 1 for field in fields):
            raise ValueError
        return tuple(data[field][0] for field in fields)

    def rate_allowed(self, handler, action):
        address = handler.client_address[0]
        # An HTTPS gate runs behind our local Cloudflare tunnel.
        if self.secure and ip_address(address).is_loopback:
            try:
                address = str(ip_address(handler.headers.get('CF-Connecting-IP', '')))
            except ValueError:
                pass
        address_limit, total_limit = (6, 36) if action == 'signup' else (12, 128)
        timestamp = time.monotonic()
        recent = self.attempts[action]
        with self.lock:
            while recent and timestamp - recent[0][0] >= 60:
                recent.popleft()
            if len(recent) >= total_limit or sum(peer == address for _, peer in recent) >= address_limit:
                return False
            recent.append((timestamp, address))
        return True

    def issue_session(self, handler):
        now = time.monotonic()
        with self.lock:
            self.sessions = {key: expiry for key, expiry in self.sessions.items() if expiry > now}
            self.sessions.pop(self.token(handler), None)
            if len(self.sessions) >= 64:
                self.sessions.pop(next(iter(self.sessions)))
            token = secrets.token_urlsafe(32)
            self.sessions[token] = now + SESSION_SECONDS
        self.redirect(handler, '/', self.cookie_header(token, SESSION_SECONDS))

    def verify_credentials(self, username, password):
        demo = bool(self.username) and hmac.compare_digest(username.encode(), self.username.encode())
        account = None
        if not demo and self.registered_accounts:
            with closing(sqlite3.connect(self.accounts_file)) as db:
                account = db.execute('SELECT salt, digest FROM accounts WHERE username = ?',
                                     (username.strip().lower(),)).fetchone()
        salt, digest = account or (self.salt, self.digest)
        matches = hmac.compare_digest(password_hash(password, salt), digest)
        return matches and (demo or account is not None)

    def login(self, handler):
        try:
            username, password = self.read_form(handler, ('username', 'password'))
            if len(username) > 64 or len(password) > 256:
                raise ValueError
        except ValueError:
            return self.auth_page(handler, 'login', 400, 'Check the username and password fields.')
        if not self.rate_allowed(handler, 'login') or not self.hash_slots.acquire(blocking=False):
            return self.auth_page(handler, 'login', 429, 'Please wait a moment and try again.')
        try:
            allowed = self.verify_credentials(username, password)
        except sqlite3.Error:
            return self.auth_page(handler, 'login', 503, 'Sign-in is temporarily unavailable.')
        finally:
            self.hash_slots.release()
        if not allowed:
            return self.auth_page(handler, 'login', 401, 'Username or password is incorrect.')
        return self.issue_session(handler)

    def register(self, handler):
        try:
            username, password, confirmation = self.read_form(handler, ('username', 'password', 'confirm'))
        except ValueError:
            return self.auth_page(handler, 'signup', 400, 'Fill out all three fields.')
        username = username.strip().lower()
        if not USERNAME.fullmatch(username):
            return self.auth_page(handler, 'signup', 400, 'Use 3–32 letters, numbers, hyphens or underscores.')
        if not 14 <= len(password) <= 256:
            return self.auth_page(handler, 'signup', 400, 'Use a password with at least 14 characters.')
        if password != confirmation:
            return self.auth_page(handler, 'signup', 400, 'The passwords do not match.')
        if not self.rate_allowed(handler, 'signup') or not self.hash_slots.acquire(blocking=False):
            return self.auth_page(handler, 'signup', 429, 'Please wait a moment and try again.')
        try:
            if username == self.username.lower():
                return self.auth_page(handler, 'signup', 409, 'That username is already taken.')
            salt = secrets.token_bytes(16)
            digest = password_hash(password, salt)
            with closing(sqlite3.connect(self.accounts_file)) as db, db:
                db.execute('INSERT INTO accounts (username, salt, digest) VALUES (?, ?, ?)',
                           (username, salt, digest))
        except sqlite3.IntegrityError:
            return self.auth_page(handler, 'signup', 409, 'That username is already taken.')
        except sqlite3.Error:
            return self.auth_page(handler, 'signup', 503, 'Account creation is temporarily unavailable.')
        finally:
            self.hash_slots.release()
        return self.issue_session(handler)

    def handle(self, handler):
        """Return True if this gate handled the request."""
        path = urlsplit(handler.path).path
        if path == '/login.css' and handler.command in ('GET', 'HEAD'):
            self.send(handler, 200, (self.dashboard / 'login.css').read_bytes(), 'text/css; charset=utf-8')
            return True
        if path == '/login-background' and handler.command in ('GET', 'HEAD'):
            try:
                body = (self.dashboard / 'room-backdrop.jpg').read_bytes()
            except OSError:
                self.send(handler, 404)
            else:
                self.send(handler, 200, body, 'image/jpeg')
            return True
        if path == '/signup' and handler.command in ('GET', 'HEAD', 'POST'):
            if not self.allow_signup:
                self.send(handler, 404)
            elif handler.command == 'POST' and not self.valid_origin(handler):
                self.send(handler, 403, b'Cross-origin request denied')
            elif self.signed_in(handler):
                self.redirect(handler, '/')
            elif handler.command == 'POST':
                self.register(handler)
            else:
                self.auth_page(handler, 'signup')
            return True
        if path in ('/login', '/logout') and handler.command == 'POST':
            if not self.valid_origin(handler):
                self.send(handler, 403, b'Cross-origin request denied')
            elif path == '/login':
                self.login(handler)
            else:
                with self.lock:
                    self.sessions.pop(self.token(handler), None)
                self.redirect(handler, '/login', self.cookie_header('', 0))
            return True
        if path == '/login' and handler.command in ('GET', 'HEAD'):
            if self.signed_in(handler):
                self.redirect(handler, '/')
            else:
                self.auth_page(handler, 'login')
            return True
        if self.signed_in(handler):
            return False
        if path == '/' and handler.command in ('GET', 'HEAD'):
            self.redirect(handler, '/login')
        else:
            self.send(handler, 401, b'{"error":"Sign in required"}', 'application/json')
        return True
