"""Static website and aggregate-only metrics; no visitor identifiers are retained."""
import json
import mimetypes
import os
from pathlib import Path
import re
import signal
import sqlite3
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE = '/lumastream'
VERSION = 'v0.9.1'
ASSETS = {'apk': 'lumastream-0.9.1-universal.apk', 'checksums': 'SHA256SUMS'}
PAGES = {'': 'home', 'download': 'download', 'guide': 'guide', 'faq': 'faq', 'privacy': 'privacy', 'credits': 'credits', 'getting-started': 'guide'}
BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)
BOT = re.compile(r'bot|crawler|spider|preview|curl|wget|prometheus|blackbox', re.I)


class Store:
    def __init__(self, directory):
        Path(directory).mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.db = sqlite3.connect(str(Path(directory) / 'analytics.sqlite'), check_same_thread=False, timeout=5)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS counters (kind TEXT, key TEXT, language TEXT, value INTEGER NOT NULL, PRIMARY KEY(kind,key,language))')
        self.db.execute('CREATE TABLE IF NOT EXISTS github (asset TEXT PRIMARY KEY, value INTEGER NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value REAL NOT NULL)')
        for language in ('en', 'ru'):
            for page in set(PAGES.values()):
                self.db.execute('INSERT OR IGNORE INTO counters VALUES (?,?,?,0)', ('page', page, language))
        for asset in ASSETS:
            self.db.execute('INSERT OR IGNORE INTO counters VALUES (?,?,?,0)', ('download', asset, ''))
        self.db.commit()
        self.requests = {}
        self.buckets = [0] * len(BUCKETS)
        self.duration_sum = 0.0
        self.duration_count = 0
        self.github_success = 0

    def increment(self, kind, key, language=''):
        with self.lock, self.db:
            self.db.execute('UPDATE counters SET value=value+1 WHERE kind=? AND key=? AND language=?', (kind, key, language))

    def healthy(self):
        with self.lock:
            return self.db.execute('SELECT 1').fetchone()[0] == 1

    def observe(self, route, status, duration):
        with self.lock:
            key = (route, str(status // 100) + 'xx')
            self.requests[key] = self.requests.get(key, 0) + 1
            self.duration_sum += duration
            self.duration_count += 1
            for i, bound in enumerate(BUCKETS):
                if duration <= bound:
                    self.buckets[i] += 1

    def github_update(self, values):
        with self.lock, self.db:
            for asset, value in values.items():
                self.db.execute('INSERT OR REPLACE INTO github VALUES (?,?)', (asset, value))
            self.db.execute('INSERT OR REPLACE INTO state VALUES (?,?)', ('github_last_success', time.time()))
            self.github_success = 1

    def metrics(self):
        with self.lock:
            out = ['# TYPE lumastream_page_views_total counter', '# TYPE lumastream_download_redirects_total counter']
            for kind, key, language, value in self.db.execute('SELECT kind,key,language,value FROM counters ORDER BY kind,key,language'):
                if kind == 'page':
                    out.append(f'lumastream_page_views_total{{page="{key}",language="{language}"}} {value}')
                else:
                    out.append(f'lumastream_download_redirects_total{{asset="{key}"}} {value}')
            out.append('# TYPE lumastream_http_requests_total counter')
            for (route, status), value in sorted(self.requests.items()):
                out.append(f'lumastream_http_requests_total{{route="{route}",status="{status}"}} {value}')
            out.append('# TYPE lumastream_http_request_duration_seconds histogram')
            for bound, count in zip(BUCKETS, self.buckets):
                out.append(f'lumastream_http_request_duration_seconds_bucket{{le="{bound}"}} {count}')
            out.extend([f'lumastream_http_request_duration_seconds_bucket{{le="+Inf"}} {self.duration_count}', f'lumastream_http_request_duration_seconds_sum {self.duration_sum}', f'lumastream_http_request_duration_seconds_count {self.duration_count}'])
            out.append('# TYPE lumastream_github_asset_downloads gauge')
            for asset, value in self.db.execute('SELECT asset,value FROM github'):
                out.append(f'lumastream_github_asset_downloads{{version="{VERSION}",asset="{asset}"}} {value}')
            last = self.db.execute('SELECT value FROM state WHERE key=?', ('github_last_success',)).fetchone()
            out.extend(['# TYPE lumastream_github_refresh_success gauge', f'lumastream_github_refresh_success {self.github_success}', '# TYPE lumastream_github_last_success_timestamp_seconds gauge', f'lumastream_github_last_success_timestamp_seconds {last[0] if last else 0}'])
            return ('\n'.join(out) + '\n').encode()

    def close(self):
        with self.lock:
            self.db.close()


def refresh_github(store):
    try:
        request = urllib.request.Request(f'https://api.github.com/repos/valdisd96/lumastream/releases/tags/{VERSION}', headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'LumaStream-website-stats'})
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read(1024 * 1024 + 1)
        if len(body) > 1024 * 1024:
            raise ValueError('Release response exceeds limit')
        release = json.loads(body)
        if release['tag_name'] != VERSION or release['draft']:
            raise ValueError('Unexpected release')
        values = {}
        for key, filename in ASSETS.items():
            entries = [x for x in release['assets'] if x['name'] == filename]
            if len(entries) != 1 or type(entries[0]['download_count']) is not int or entries[0]['download_count'] < 0:
                raise ValueError('Invalid release asset count')
            values[key] = entries[0]['download_count']
        store.github_update(values)
    except Exception:
        with store.lock:
            store.github_success = 0
        print('GitHub statistics refresh failed; previous sample retained.', flush=True)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 32

    def __init__(self, address, store, static_dir, metrics=False):
        self.store = store
        self.static_dir = Path(static_dir).resolve()
        self.metrics_only = metrics
        self.slots = threading.BoundedSemaphore(32)
        super().__init__(address, Handler)

    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.slots.release()

    def handle_error(self, request, client_address):
        print('HTTP connection failed.', flush=True)


class Handler(BaseHTTPRequestHandler):
    server_version = 'LumaStream'
    sys_version = ''

    def setup(self):
        self.request.settimeout(10)
        super().setup()

    def log_message(self, *args):
        pass

    def send_error(self, code, message=None, explain=None):
        self.respond(code, b'Request rejected\n')

    def respond(self, status, body=b'', content_type='text/plain; charset=utf-8', location=None):
        self.status = status
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        self.send_header('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        self.send_header('Cache-Control', 'no-store' if location or 'text/html' in content_type or getattr(self, 'route', 'unknown') != 'asset' else 'public, max-age=3600')
        if location:
            self.send_header('Location', location)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        started = time.monotonic()
        self.route, self.status = 'unknown', 500
        try:
            self.serve()
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass
        except (OSError, sqlite3.Error, ValueError):
            self.respond(503, b'Service temporarily unavailable\n')
        finally:
            if not self.server.metrics_only and self.route != 'health':
                self.server.store.observe(self.route, self.status, time.monotonic() - started)

    def serve(self):
        path = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)
        store = self.server.store
        if self.server.metrics_only:
            if path == '/metrics':
                self.route = 'metrics'
                return self.respond(200, store.metrics(), 'text/plain; version=0.0.4; charset=utf-8')
            return self.respond(404, b'Not found\n')
        if path in ('/healthz', BASE + '/healthz'):
            self.route = 'health'
            return self.respond(200 if store.healthy() else 503, b'ok\n')
        if path == BASE:
            self.route = 'canonical'
            return self.respond(308, location=BASE + '/')
        if not path.startswith(BASE + '/'):
            return self.respond(404, b'Not found\n')
        relative = path[len(BASE) + 1:]
        if '\x00' in relative or '\\' in relative or '..' in relative.split('/'):
            return self.respond(404, b'Not found\n')
        human = not BOT.search(self.headers.get('User-Agent', '')) and 'prefetch' not in (self.headers.get('Sec-Purpose', '') + self.headers.get('Purpose', '')).lower()
        if relative.startswith('download/') and relative.split('/')[-1] in ASSETS and relative.count('/') == 1:
            asset = relative.split('/')[-1]
            self.route = 'download_redirect'
            if self.command == 'GET' and human:
                store.increment('download', asset)
            return self.respond(302, location=f'https://github.com/valdisd96/lumastream/releases/download/{VERSION}/{ASSETS[asset]}')
        target = (self.server.static_dir / relative).resolve()
        if not target.is_relative_to(self.server.static_dir):
            return self.respond(404, b'Not found\n')
        if target.is_dir():
            if not path.endswith('/'):
                self.route = 'canonical'
                return self.respond(308, location=urllib.parse.quote(path, safe='/') + '/')
            target = (target / 'index.html').resolve()
        if not target.is_relative_to(self.server.static_dir) or not target.is_file():
            return self.respond(404, b'Not found\n')
        language = 'ru' if relative.startswith('ru/') else 'en'
        slug = relative[3:] if language == 'ru' else relative
        slug = slug.removesuffix('index.html').strip('/').removesuffix('.html')
        content_type = mimetypes.guess_type(str(target))[0] or 'application/octet-stream'
        if content_type.startswith('text/'):
            content_type += '; charset=utf-8'
        body = target.read_bytes()
        if slug in PAGES and 'text/html' in content_type:
            self.route = 'page'
            if self.command == 'GET' and human:
                store.increment('page', PAGES[slug], language)
        else:
            self.route = 'asset'
        self.respond(200, body, content_type)


def main():
    store = Store(os.environ.get('DATA_DIR', '.local/data'))
    root = os.environ.get('STATIC_DIR', 'public')
    servers = [Server(('0.0.0.0', int(os.environ.get('PORT', '8080'))), store, root), Server(('0.0.0.0', int(os.environ.get('METRICS_PORT', '9090'))), store, root, True)]
    stop = threading.Event()
    def shutdown(signum, frame):
        stop.set()
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    def updater():
        while not stop.is_set():
            refresh_github(store)
            stop.wait(900)
    worker = threading.Thread(target=updater, daemon=True)
    worker.start()
    for server in servers:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    print('LumaStream website and private metrics ready.', flush=True)
    stop.wait()
    for server in servers:
        server.shutdown()
        server.server_close()
    worker.join(timeout=12)
    # Daemon request threads may still be unwinding; process exit closes SQLite.


if __name__ == '__main__':
    main()
