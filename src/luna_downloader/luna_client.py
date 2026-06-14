from __future__ import annotations

import re
import socket
import time
from html import unescape
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from .models import ConnectionStatus, LunaFile

DEFAULT_HOST = "192.168.42.1"
DEFAULT_CAMERA_URL = f"http://{DEFAULT_HOST}/storage_internal/DCIM/Camera01/"

AUTH_PAYLOADS = [
    bytes(
        [
            0x55,
            0x43,
            0x44,
            0x32,
            0x01,
            0x0C,
            0x05,
            0x0F,
            0x00,
            0x00,
            0x00,
            0x00,
            0x37,
            0x05,
            0x47,
            0x7C,
        ]
    ),
    bytes(
        [
            0x55,
            0x43,
            0x44,
            0x32,
            0x01,
            0x0C,
            0x04,
            0x10,
            0x0F,
            0x00,
            0x00,
            0x00,
            0x08,
            0x00,
            0x02,
            0x01,
            0x00,
            0x00,
            0x80,
            0x00,
            0x00,
            0x08,
            0x30,
            0x08,
            0x0F,
            0x08,
            0x0B,
            0x7C,
            0x00,
            0x8E,
            0x7C,
        ]
    ),
]

INDEX_RE = re.compile(
    r'<a href="(?P<href>[^"]+)">(?P<name>[^<]+)</a>\s+'
    r"(?P<date>\d{2}-[A-Za-z]{3}-\d{4})\s+"
    r"(?P<time>\d{2}:\d{2})\s+"
    r"(?P<size>\S+)",
    re.IGNORECASE,
)


def parse_size(text: str) -> int | None:
    match = re.fullmatch(r"(?P<number>\d+(?:\.\d+)?)(?P<unit>[KMG])?", text.strip())
    if not match:
        return None

    number = float(match.group("number"))
    unit = match.group("unit")
    multiplier = {"K": 1024, "M": 1024**2, "G": 1024**3}.get(unit, 1)
    return int(number * multiplier)


def file_kind(name: str) -> str:
    suffix = name.rsplit(".", 1)[-1].upper() if "." in name else ""
    if suffix in {"MP4", "LRV"}:
        return suffix
    return "FILE"


def parse_luna_index(html: str, base_url: str = DEFAULT_CAMERA_URL) -> list[LunaFile]:
    files: list[LunaFile] = []
    for match in INDEX_RE.finditer(html):
        name = unescape(match.group("name"))
        href = unescape(match.group("href"))
        if name == "../" or href == "../":
            continue

        size_text = match.group("size")
        files.append(
            LunaFile(
                name=name,
                href=href,
                url=urljoin(base_url, href),
                date=match.group("date"),
                time=match.group("time"),
                size_text=size_text,
                bytes=parse_size(size_text),
                kind=file_kind(name),
            )
        )
    return files


class LunaAuthSession:
    def __init__(self, host: str = DEFAULT_HOST, port: int = 6666, timeout: float = 3.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._socket: socket.socket | None = None

    @property
    def is_open(self) -> bool:
        return self._socket is not None

    def open(self) -> None:
        if self._socket is not None:
            return

        last_error: OSError | None = None
        for _attempt in range(3):
            sock: socket.socket | None = None
            try:
                sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
                sock.settimeout(self.timeout)
                for payload in AUTH_PAYLOADS:
                    sock.sendall(payload)
                    time.sleep(0.03)
                self._drain_response(sock)
                self._socket = sock
                return
            except OSError as exc:
                last_error = exc
                if sock is not None:
                    sock.close()
                time.sleep(0.2)

        if last_error is not None:
            raise last_error
        raise ConnectionError(f"Could not open Luna control session to {self.host}:{self.port}")

    def close(self) -> None:
        if self._socket is not None:
            self._socket.close()
            self._socket = None

    def __enter__(self) -> "LunaAuthSession":
        self.open()
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.close()

    def _drain_response(self, sock: socket.socket) -> None:
        deadline = time.monotonic() + 0.2
        sock.settimeout(0.05)
        while time.monotonic() < deadline:
            try:
                data = sock.recv(65536)
            except socket.timeout:
                return
            if not data:
                return
        sock.settimeout(self.timeout)


class LunaClient:
    def __init__(self, host: str = DEFAULT_HOST):
        self.host = host
        self.camera_url = f"http://{host}/storage_internal/DCIM/Camera01/"
        self.auth_session: LunaAuthSession | None = None

    def connect(self) -> None:
        self.auth_session = LunaAuthSession(self.host)
        self.auth_session.open()

    def close(self) -> None:
        if self.auth_session is not None:
            self.auth_session.close()
            self.auth_session = None

    def list_files(self) -> list[LunaFile]:
        request = Request(
            self.camera_url,
            headers={"User-Agent": "Insta360 Luna Downloader/0.1"},
        )
        with urlopen(request, timeout=5) as response:
            html = response.read().decode("utf-8", errors="replace")
        return parse_luna_index(html, self.camera_url)

    def check_status(self) -> ConnectionStatus:
        http_ok = False
        control_ok = False
        message = "未连接"

        try:
            with socket.create_connection((self.host, 80), timeout=2):
                http_ok = True
        except OSError as exc:
            message = f"HTTP 服务不可用：{exc}"

        try:
            with socket.create_connection((self.host, 6666), timeout=2):
                control_ok = True
        except OSError as exc:
            if http_ok:
                message = f"控制端口不可用：{exc}"

        if http_ok and control_ok:
            message = "已检测到 Luna 相机"

        return ConnectionStatus(self.host, http_ok, control_ok, message)
