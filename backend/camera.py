"""Catalog and stream the locally installed GMDCSA-24 clips."""
import json
import os
import re
from pathlib import Path


VIDEO_PREFIX = '/media/gmdcsa24/'
CLIP_PATH = re.compile(r'Subject ([1-4])/(ADL|Fall)/([0-9]{2})\.mp4')
BYTE_RANGE = re.compile(r'bytes=([0-9]{0,20})-([0-9]{0,20})', re.IGNORECASE)
CHUNK_SIZE = 128 * 1024


def clip_titles(root):
    try:
        manifest = json.loads((root / 'annotations.json').read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return {}
    if not isinstance(manifest, dict) or not isinstance(manifest.get('clips'), list):
        return {}
    return {
        clip['path']: clip['description'].strip()
        for clip in manifest['clips']
        if isinstance(clip, dict) and isinstance(clip.get('path'), str)
        and isinstance(clip.get('description'), str)
    }


def byte_bounds(header, size):
    """Return inclusive bounds for a single byte range, or None if invalid."""
    match = BYTE_RANGE.fullmatch(header.strip())
    if match is None or size == 0:
        return None
    first, last = match.groups()
    if not first:
        if not last or int(last) == 0:
            return None
        return max(0, size - int(last)), size - 1
    start = int(first)
    end = min(int(last), size - 1) if last else size - 1
    return (start, end) if start <= end else None


class CameraDataset:
    def __init__(self, directory):
        self.clips = []
        self.paths = {}
        if not directory:
            return
        try:
            root = Path(directory).resolve(strict=True)
        except (OSError, RuntimeError):
            return
        if not root.is_dir():
            return
        titles = clip_titles(root)
        for path in sorted(root.glob('Subject */*/*.mp4')):
            key = path.relative_to(root).as_posix()
            match = CLIP_PATH.fullmatch(key)
            if not match:
                continue
            try:
                file = path.resolve(strict=True)
                if not file.is_relative_to(root) or not file.is_file():
                    continue
            except (OSError, RuntimeError):
                continue
            person, category, number = match.groups()
            subject = f'Subject {person}'
            clip_id = f'subject-{person}-{category.lower()}-{number}'
            url = f'{VIDEO_PREFIX}{clip_id}.mp4'
            self.paths[url] = file
            self.clips.append({
                'id': clip_id,
                'subject': subject,
                'category': category.lower(),
                'title': titles.get(key) or f'{subject} · {category} {number}',
                'url': url,
            })

    def stream(self, handler, url):
        """Write a video response and return True, or leave an unknown clip to the router."""
        file = self.paths.get(url)
        if file is None:
            return False
        try:
            if file.resolve(strict=True) != file or not file.is_file():
                return False
            source = file.open('rb')
        except (OSError, RuntimeError):
            return False
        with source:
            size = os.fstat(source.fileno()).st_size
            range_header = handler.headers.get('Range') if handler.command == 'GET' else None
            if range_header is None:
                bounds, status = (0, size - 1), 200
            else:
                bounds = byte_bounds(range_header, size)
                status = 206 if bounds is not None else 416
            length = 0 if bounds is None else bounds[1] - bounds[0] + 1
            handler.send_response(status)
            handler.send_header('Content-Type', 'video/mp4')
            handler.send_header('Content-Length', str(length))
            handler.send_header('Accept-Ranges', 'bytes')
            handler.send_header('Cache-Control', 'private, no-store')
            handler.send_header('X-Content-Type-Options', 'nosniff')
            if status == 416:
                handler.send_header('Content-Range', f'bytes */{size}')
            elif status == 206:
                handler.send_header('Content-Range', f'bytes {bounds[0]}-{bounds[1]}/{size}')
            handler.end_headers()
            if bounds is not None and handler.command == 'GET':
                source.seek(bounds[0])
                try:
                    while length:
                        chunk = source.read(min(CHUNK_SIZE, length))
                        if not chunk:
                            break
                        handler.wfile.write(chunk)
                        length -= len(chunk)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass
        return True
