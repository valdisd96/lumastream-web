import http.client
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import server


class WebsiteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.public = root / 'public'
        self.public.mkdir()
        (self.public / 'index.html').write_text('<h1>Website</h1>')
        (self.public / 'asset.css').write_text('body{}')
        (root / 'private.txt').write_text('secret')
        (self.public / 'escape').symlink_to(root / 'private.txt')
        self.data = root / 'data'
        self.store = server.Store(self.data)
        self.web = server.Server(('127.0.0.1', 0), self.store, self.public)
        self.metrics = server.Server(('127.0.0.1', 0), self.store, self.public, True)
        self.threads = []
        for s in (self.web, self.metrics):
            thread = threading.Thread(target=s.serve_forever)
            thread.start()
            self.threads.append(thread)

    def tearDown(self):
        for s in (self.web, self.metrics):
            s.shutdown()
            s.server_close()
        for t in self.threads:
            t.join()
        self.store.close()
        self.tmp.cleanup()

    def request(self, path, method='GET', headers=None, metrics=False):
        conn = http.client.HTTPConnection('127.0.0.1', (self.metrics if metrics else self.web).server_port, timeout=3)
        conn.request(method, path, headers=headers or {'User-Agent': 'Mozilla/5.0'})
        response = conn.getresponse()
        result = (response.status, dict(response.getheaders()), response.read())
        conn.close()
        return result

    def test_count_only_successful_human_html_gets(self):
        self.assertEqual(self.request('/lumastream/?utm_source=ignored')[0], 200)
        self.assertEqual(self.request('/lumastream/', 'HEAD')[2], b'')
        for path in ('/healthz', '/lumastream/healthz', '/lumastream/asset.css', '/lumastream/missing'):
            self.request(path)
        self.request('/lumastream/', headers={'User-Agent': 'ExampleBot'})
        self.request('/lumastream/', headers={'Sec-Purpose': 'prefetch'})
        text = self.store.metrics().decode()
        self.assertIn('lumastream_page_views_total{page="home",language="en"} 1\n', text)
        self.assertNotIn('utm_source', text)
        self.assertNotIn('missing', text)

    def test_download_redirect_exact_and_head_does_not_count(self):
        status, headers, _ = self.request('/lumastream/download/apk')
        self.assertEqual(status, 302)
        self.assertEqual(headers['Location'], 'https://github.com/valdisd96/lumastream/releases/download/v0.9.1/lumastream-0.9.1-universal.apk')
        self.request('/lumastream/download/apk', 'HEAD')
        self.assertIn('lumastream_download_redirects_total{asset="apk"} 1\n', self.store.metrics().decode())
        self.assertEqual(self.request('/lumastream/download/arbitrary')[0], 404)

    def test_traversal_and_symlink_escape_are_rejected(self):
        for path in ('/lumastream/../private.txt', '/lumastream/%2e%2e/private.txt', '/lumastream/escape', '/lumastream/%00'):
            with self.subTest(path=path):
                status, _, body = self.request(path)
                self.assertEqual(status, 404)
                self.assertNotIn(b'secret', body)

    def test_metrics_listener_is_private_and_unknown_paths_bounded(self):
        for path in ('/metrics', '/lumastream/metrics'):
            self.assertEqual(self.request(path)[0], 404)
        for i in range(10):
            self.request('/random/' + str(i))
        status, _, body = self.request('/metrics', metrics=True)
        self.assertEqual(status, 200)
        self.assertIn(b'route="unknown",status="4xx"} 12', body)
        self.assertEqual(self.request('/lumastream/', metrics=True)[0], 404)

    def test_durable_counts_and_github_sample_survive_reopen(self):
        self.store.increment('page', 'home', 'ru')
        self.store.github_update({'apk': 7, 'checksums': 4})
        other = server.Store(self.data)
        try:
            text = other.metrics().decode()
            self.assertIn('page="home",language="ru"} 1', text)
            self.assertIn('version="v0.9.1",asset="apk"} 7', text)
            self.assertNotIn('last_success_timestamp_seconds 0\n', text)
        finally:
            other.close()

    def test_refresh_failure_retains_sample_and_reports_failure(self):
        self.store.github_update({'apk': 7, 'checksums': 4})
        with patch('server.urllib.request.urlopen', side_effect=OSError('offline')):
            server.refresh_github(self.store)
        text = self.store.metrics().decode()
        self.assertIn('asset="apk"} 7', text)
        self.assertIn('lumastream_github_refresh_success 0', text)

    def test_storage_failure_does_not_issue_counted_download(self):
        with patch.object(self.store, 'increment', side_effect=server.sqlite3.OperationalError('full')):
            status, headers, _ = self.request('/lumastream/download/apk')
        self.assertEqual(status, 503)
        self.assertNotIn('Location', headers)

    def test_unsupported_method_and_canonical_redirect(self):
        self.assertEqual(self.request('/lumastream/', 'POST')[0], 501)
        status, headers, _ = self.request('/lumastream')
        self.assertEqual(status, 308)
        self.assertEqual(headers['Location'], '/lumastream/')


if __name__ == '__main__':
    unittest.main()
