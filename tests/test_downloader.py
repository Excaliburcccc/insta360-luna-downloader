import http.server
import threading
from pathlib import Path

from luna_downloader.downloader import download_file
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


def test_download_file_resumes_from_existing_bytes(tmp_path: Path):
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RangeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    dest = tmp_path / "sample.mp4"
    dest.write_bytes(b"0123")
    port = server.server_address[1]
    item = LunaFile(
        name="sample.mp4",
        href="sample.mp4",
        url=f"http://127.0.0.1:{port}/sample.mp4",
        date="14-Jun-2026",
        time="12:13",
        size_text="16",
        bytes=16,
        kind="MP4",
    )

    progress = []
    try:
        result = download_file(item, dest, progress.append)
    finally:
        server.shutdown()

    assert result == dest
    assert dest.read_bytes() == RangeHandler.payload
    assert RangeHandler.ranges[-1] == "bytes=4-"
    assert progress[-1].downloaded == 16
    assert progress[-1].total == 16
