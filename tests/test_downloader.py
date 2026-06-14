import http.server
import threading
from pathlib import Path

import pytest

from luna_downloader.downloader import DownloadCancelled, download_file
from luna_downloader.models import LunaFile


class RangeHandler(http.server.BaseHTTPRequestHandler):
    payload = b"0123456789abcdef"
    ranges = []

    def do_GET(self):
        RangeHandler.ranges.append(self.headers.get("Range"))
        start = 0
        range_header = self.headers.get("Range")
        if range_header:
            start = int(range_header.removeprefix("bytes=").removesuffix("-"))
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{len(self.payload)-1}/{len(self.payload)}")
        else:
            self.send_response(200)
        body = self.payload[start:]
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format, *_args):
        return


class IgnoreRangeHandler(http.server.BaseHTTPRequestHandler):
    payload = b"0123456789abcdef"
    ranges = []

    def do_GET(self):
        IgnoreRangeHandler.ranges.append(self.headers.get("Range"))
        self.send_response(200)
        self.send_header("Content-Length", str(len(self.payload)))
        self.end_headers()
        self.wfile.write(self.payload)

    def log_message(self, _format, *_args):
        return


def make_item(port: int, name: str = "sample.mp4", size: int = 16) -> LunaFile:
    return LunaFile(
        name=name,
        href=name,
        url=f"http://127.0.0.1:{port}/{name}",
        date="14-Jun-2026",
        time="12:13",
        size_text=str(size),
        bytes=size,
        kind="MP4",
    )


def test_download_file_resumes_from_existing_bytes(tmp_path: Path):
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RangeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    dest = tmp_path / "sample.mp4"
    part = dest.with_name(dest.name + ".part")
    part.write_bytes(b"0123")
    port = server.server_address[1]
    item = make_item(port)

    progress = []
    try:
        result = download_file(item, dest, progress.append)
    finally:
        server.shutdown()

    assert result == dest
    assert dest.read_bytes() == RangeHandler.payload
    assert not part.exists()
    assert RangeHandler.ranges[-1] == "bytes=4-"
    assert progress[-1].downloaded == 16
    assert progress[-1].total == 16


def test_download_file_writes_part_file_until_complete(tmp_path: Path):
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RangeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    dest = tmp_path / "sample.mp4"
    item = make_item(server.server_address[1])
    final_visible_during_progress = []

    def on_progress(_progress):
        final_visible_during_progress.append(dest.exists())

    try:
        result = download_file(item, dest, on_progress, chunk_size=4)
    finally:
        server.shutdown()

    assert result == dest
    assert final_visible_during_progress
    assert not any(final_visible_during_progress)
    assert dest.read_bytes() == RangeHandler.payload
    assert not dest.with_name(dest.name + ".part").exists()


def test_download_file_restarts_part_when_server_ignores_range(tmp_path: Path):
    IgnoreRangeHandler.ranges = []
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), IgnoreRangeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    dest = tmp_path / "sample.mp4"
    part = dest.with_name(dest.name + ".part")
    part.write_bytes(b"0123")
    item = make_item(server.server_address[1])

    try:
        result = download_file(item, dest)
    finally:
        server.shutdown()

    assert result == dest
    assert IgnoreRangeHandler.ranges[-1] == "bytes=4-"
    assert dest.read_bytes() == IgnoreRangeHandler.payload
    assert not part.exists()


def test_download_file_cancel_keeps_part_and_does_not_create_final_file(tmp_path: Path):
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RangeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    dest = tmp_path / "sample.mp4"
    item = make_item(server.server_address[1])
    cancel_event = threading.Event()

    def on_progress(progress):
        if progress.downloaded >= 4:
            cancel_event.set()

    try:
        with pytest.raises(DownloadCancelled):
            download_file(item, dest, on_progress, cancel_event, chunk_size=4)
    finally:
        server.shutdown()

    part = dest.with_name(dest.name + ".part")
    assert not dest.exists()
    assert part.exists()
    assert part.read_bytes() == RangeHandler.payload[:4]
