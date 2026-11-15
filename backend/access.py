"""Password gate for a small Home IoT demo."""
import hashlib
import hmac
import json
import secrets
import threading
import time
from http.cookies import CookieError, SimpleCookie
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


ROUNDS = 600_000
SESSION_SECONDS = 8 * 60 * 60
CSP = ("default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self'; "
       "connect-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'")


def password_hash(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, ROUNDS)


class AccessGate:
    def __init__(self, account_file, dashboard, secure=False):
        settings = json.loads(Path(account_file).read_text(encoding='utf-8'))
        self.username = settings['username']
        self.salt = bytes.fromhex(settings['salt'])
        self.digest = bytes.fromhex(settings['digest'])
        if not self.username or len(self.salt) != 16 or len(self.digest) != 32:
            raise ValueError('Invalid demo login configuration')
        self.secure = secure
        self.cookie_name = '__Host-home_iot_session' if secure else 'home_iot_session'
        self.dashboard = Path(dashboard)
        self.sessions = {}
        self.failed = []
        self.lock = threading.Lock()

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

    def login_page(self, handler, status=200, message=''):
        page = (self.dashboard / 'login.html').read_bytes()
        self.send(handler, status, page.replace(b'<!-- login-message -->', message.encode('utf-8')))

    def valid_origin(self, handler):
        origin = handler.headers.get('Origin')
        if handler.headers.get('Sec-Fetch-Site') == 'cross-site':
            return False
        return not origin or urlsplit(origin).netloc == handler.headers.get('Host')

    def login(self, handler):
        kind = handler.headers.get('Content-Type', '').split(';', 1)[0]
        try:
            length = int(handler.headers.get('Content-Length', '0'))
            if kind != 'application/x-www-form-urlencoded' or not 0 < length <= 2048:
                raise ValueError
            data = parse_qs(handler.rfile.read(length).decode('utf-8'), max_num_fields=3)
            username, password = data['username'][0], data['password'][0]
            if len(username) > 64 or len(password) > 256:
                raise ValueError
        except (KeyError, ValueError):
            return self.login_page(handler, 400, 'Check the username and password fields.')

        with self.lock:
            now = time.monotonic()
            self.failed[:] = [attempt for attempt in self.failed if now - attempt < 60]
            if len(self.failed) >= 10:
                status, message = 429, 'Please wait one minute and try again.'
                token = None
            elif not (hmac.compare_digest(password_hash(password, self.salt), self.digest) and
                      hmac.compare_digest(username.encode(), self.username.encode())):
                self.failed.append(now)
                status, message = 401, 'Username or password is incorrect.'
                token = None
            else:
                self.sessions = {key: expiry for key, expiry in self.sessions.items() if expiry > now}
                self.sessions.pop(self.token(handler), None)
                if len(self.sessions) >= 64:
                    self.sessions.pop(next(iter(self.sessions)))
                token = secrets.token_urlsafe(32)
                self.sessions[token] = now + SESSION_SECONDS
        if token is None:
            return self.login_page(handler, status, message)
        self.redirect(handler, '/', self.cookie_header(token, SESSION_SECONDS))

    def handle(self, handler):
        """Return True if this gate handled the request."""
        path = urlsplit(handler.path).path
        if path == '/login.css' and handler.command in ('GET', 'HEAD'):
            self.send(handler, 200, (self.dashboard / 'login.css').read_bytes(), 'text/css; charset=utf-8')
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
                self.login_page(handler)
            return True
        if self.signed_in(handler):
            return False
        if path == '/' and handler.command in ('GET', 'HEAD'):
            self.redirect(handler, '/login')
        else:
            self.send(handler, 401, b'{"error":"Sign in required"}', 'application/json')
        return True
