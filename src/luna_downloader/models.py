from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LunaFile:
    name: str
    href: str
    url: str
    date: str
    time: str
    size_text: str
    bytes: int | None
    kind: str


@dataclass(frozen=True)
class DownloadProgress:
    file_name: str
    downloaded: int
    total: int | None
    speed_bps: float


@dataclass(frozen=True)
class ConnectionStatus:
    host: str
    http_ok: bool
    control_ok: bool
    message: str

