from __future__ import annotations

import re
import threading
import time
from http.client import RemoteDisconnected
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .models import DownloadProgress, LunaFile

ProgressCallback = Callable[[DownloadProgress], None]
CONTENT_RANGE_TOTAL_RE = re.compile(r"bytes\s+(?:\d+-\d+|\*)/(?P<total>\d+)", re.IGNORECASE)


class DownloadCancelled(Exception):
    def __init__(self, partial_path: Path):
        super().__init__("Download cancelled")
        self.partial_path = partial_path


def partial_path_for(destination: Path) -> Path:
    return destination.with_name(destination.name + ".part")


def parse_content_range_total(value: str | None) -> int | None:
    if not value:
        return None
    match = CONTENT_RANGE_TOTAL_RE.fullmatch(value.strip())
    if not match:
        return None
    return int(match.group("total"))


def parse_content_length(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def exact_total_from_response(response, existing: int) -> int | None:
    content_range_total = parse_content_range_total(response.headers.get("Content-Range"))
    if content_range_total is not None:
        return content_range_total

    content_length = parse_content_length(response.headers.get("Content-Length"))
    if content_length is None:
        return None

    status = getattr(response, "status", response.getcode())
    if status == 206:
        return existing + content_length
    return content_length


def request_headers() -> dict[str, str]:
    return {"User-Agent": "Insta360 Luna Downloader/0.1", "Accept-Encoding": "identity"}


def probe_exact_total(item: LunaFile) -> int | None:
    headers = request_headers()
    headers["Range"] = "bytes=0-0"
    request = Request(item.url, headers=headers)
    try:
        with urlopen(request, timeout=10) as response:
            return exact_total_from_response(response, 0)
    except HTTPError as exc:
        return parse_content_range_total(exc.headers.get("Content-Range"))
    except OSError:
        return None


def download_file(
    item: LunaFile,
    destination: Path,
    progress: ProgressCallback | None = None,
    cancel_event: threading.Event | None = None,
    chunk_size: int = 1024 * 256,
) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)

    partial_path = partial_path_for(destination)
    display_total = item.bytes
    exact_total: int | None = None

    if destination.exists() and not partial_path.exists():
        size = destination.stat().st_size
        if progress:
            progress(DownloadProgress(item.name, size, size, 0.0))
        return destination

    if destination.exists():
        if partial_path.exists():
            partial_path.unlink()
        destination.replace(partial_path)

    existing = partial_path.stat().st_size if partial_path.exists() else 0
    if existing > 0:
        exact_total = probe_exact_total(item)
        if exact_total is not None:
            display_total = exact_total
            if existing >= exact_total:
                if progress:
                    progress(DownloadProgress(item.name, exact_total, exact_total, 0.0))
                partial_path.replace(destination)
                return destination

    headers = request_headers()
    if existing > 0:
        headers["Range"] = f"bytes={existing}-"

    request = Request(item.url, headers=headers)
    try:
        response = urlopen(request, timeout=10)
    except HTTPError as exc:
        if existing > 0 and exc.code == 416:
            exact_total = parse_content_range_total(exc.headers.get("Content-Range")) or exact_total
            if exact_total is not None and existing >= exact_total:
                if progress:
                    progress(DownloadProgress(item.name, exact_total, exact_total, 0.0))
                partial_path.replace(destination)
                return destination
            partial_path.unlink(missing_ok=True)
            existing = 0
            request = Request(item.url, headers=request_headers())
            response = urlopen(request, timeout=10)
        else:
            raise
    except RemoteDisconnected:
        if existing > 0:
            exact_total = probe_exact_total(item)
            if exact_total is not None and existing >= exact_total:
                if progress:
                    progress(DownloadProgress(item.name, exact_total, exact_total, 0.0))
                partial_path.replace(destination)
                return destination
        raise

    status = getattr(response, "status", response.getcode())
    if existing > 0 and status == 200:
        partial_path.unlink(missing_ok=True)
        existing = 0
    elif existing > 0 and status != 206:
        response.close()
        raise OSError(f"Unexpected HTTP status {status} while resuming {item.name}")

    exact_total = exact_total_from_response(response, existing)
    progress_total = exact_total if exact_total is not None else display_total

    if progress and existing > 0:
        progress(DownloadProgress(item.name, existing, progress_total, 0.0))

    mode = "ab" if existing > 0 else "wb"
    downloaded = existing
    started_at = time.monotonic()
    last_progress_at = 0.0
    emitted_after_write = False

    def emit_progress(force: bool = False) -> None:
        nonlocal last_progress_at, emitted_after_write
        if not progress:
            return
        now = time.monotonic()
        if not force and emitted_after_write and now - last_progress_at < 0.1:
            return
        elapsed = max(now - started_at, 0.001)
        progress(
            DownloadProgress(
                item.name,
                downloaded,
                progress_total,
                (downloaded - existing) / elapsed,
            )
        )
        emitted_after_write = True
        last_progress_at = now

    try:
        with response, partial_path.open(mode) as output:
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    raise DownloadCancelled(partial_path)

                chunk = response.read(chunk_size)
                if not chunk:
                    break

                output.write(chunk)
                downloaded += len(chunk)
                emit_progress(force=exact_total is not None and downloaded >= exact_total)

                if exact_total is not None and downloaded >= exact_total:
                    break
    except DownloadCancelled:
        raise

    if exact_total is not None and downloaded < exact_total:
        raise OSError(f"Incomplete download for {item.name}: {downloaded}/{exact_total} bytes")

    emit_progress(force=True)
    partial_path.replace(destination)
    return destination
