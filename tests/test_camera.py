import json
import os
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path
from unittest.mock import patch

from backend.app import create_server
from backend.camera import CameraDataset


class CameraTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        root = Path(cls.temp.name)
        adl = root / 'Subject 1' / 'ADL'
        fall = root / 'Subject 4' / 'Fall'
        adl.mkdir(parents=True)
        fall.mkdir(parents=True)
        (adl / '08.mp4').write_bytes(b'0123456789')
        (fall / '07.mp4').write_bytes(b'abc')
        (adl / 'sample.mp4').write_bytes(b'not part of this dataset')
        (root / 'annotations.json').write_text(json.dumps({'clips': [
            {'path': 'Subject 1/ADL/08.mp4', 'description': 'Walking across the room'},
        ]}), encoding='utf-8')

        cls.server = create_server(None, {}, port=0, dataset_dir=root)
        cls.addClassCleanup(cls.server.server_close)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.addClassCleanup(cls.thread.join)
        cls.addClassCleanup(cls.server.shutdown)

    def request(self, path, method='GET', headers=None, server=None):
        conn = HTTPConnection('127.0.0.1', (server or self.server).server_port, timeout=4)
        try:
            conn.request(method, path, headers=headers or {})
            response = conn.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            conn.close()

    def test_catalog_lists_dataset_files_and_falls_back_to_file_name(self):
        status, _, body = self.request('/api/camera/clips')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {'clips': [
            {'id': 'subject-1-adl-08', 'subject': 'Subject 1', 'category': 'adl',
             'title': 'Walking across the room', 'url': '/media/gmdcsa24/subject-1-adl-08.mp4'},
            {'id': 'subject-4-fall-07', 'subject': 'Subject 4', 'category': 'fall',
             'title': 'Subject 4 · Fall 07', 'url': '/media/gmdcsa24/subject-4-fall-07.mp4'},
        ]})
        self.assertEqual(CameraDataset(None).clips, [])

    def test_serves_bundled_clips_when_external_catalog_is_unavailable(self):
        with tempfile.TemporaryDirectory() as empty_dir, patch.dict(os.environ):
            for configured in (None, empty_dir):
                with self.subTest(configured=configured):
                    if configured is None:
                        os.environ.pop('HOME_IOT_DATASET_DIR', None)
                    else:
                        os.environ['HOME_IOT_DATASET_DIR'] = configured
                    with create_server(None, {}, port=0) as server:
                        thread = threading.Thread(target=server.serve_forever, daemon=True)
                        thread.start()
                        try:
                            status, _, body = self.request('/api/camera/clips', server=server)
                            self.assertEqual(status, 200)
                            clips = json.loads(body)['clips']
                            self.assertEqual([clip['id'] for clip in clips], [
                                'subject-1-adl-13', 'subject-4-fall-07',
                            ])
                            for clip in clips:
                                status, headers, body = self.request(
                                    clip['url'], headers={'Range': 'bytes=0-31'}, server=server,
                                )
                                self.assertEqual(status, 206)
                                self.assertEqual(headers['Content-Type'], 'video/mp4')
                                self.assertEqual(body[4:8], b'ftyp')
                        finally:
                            server.shutdown()
                            thread.join()

    def test_writes_video_bytes_and_allows_head_without_body(self):
        url = '/media/gmdcsa24/subject-1-adl-08.mp4'
        status, headers, body = self.request(url)
        self.assertEqual((status, body), (200, b'0123456789'))
        self.assertEqual(headers['Content-Type'], 'video/mp4')
        self.assertEqual(headers['Accept-Ranges'], 'bytes')
        self.assertEqual(headers['Content-Length'], '10')
        status, headers, body = self.request(url, method='HEAD')
        self.assertEqual((status, headers['Content-Length'], body), (200, '10', b''))
        self.assertEqual(self.request('/media/gmdcsa24/sample.mp4')[0], 404)

    def test_ranges_are_limited_to_file_bounds(self):
        url = '/media/gmdcsa24/subject-1-adl-08.mp4'
        for value, expected, bounds in (
            ('bytes=2-4', b'234', 'bytes 2-4/10'),
            ('bytes=6-', b'6789', 'bytes 6-9/10'),
            ('bytes=-3', b'789', 'bytes 7-9/10'),
            ('bytes=9-999', b'9', 'bytes 9-9/10'),
        ):
            with self.subTest(value=value):
                status, headers, body = self.request(url, headers={'Range': value})
                self.assertEqual((status, headers['Content-Range'], body), (206, bounds, expected))
                self.assertEqual(headers['Content-Length'], str(len(expected)))
        for value in ('bytes=10-', 'bytes=4-2', 'bytes=2-4,6-8'):
            with self.subTest(value=value):
                status, headers, body = self.request(url, headers={'Range': value})
                self.assertEqual((status, headers['Content-Range'], body), (416, 'bytes */10', b''))
