from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .models import DownloadProgress, LunaFile

ProgressCallback = Callable[[DownloadProgress], None]


class DownloadCancelled(Exception):
    def __init__(self, partial_path: Path):
        super().__init__("Download cancelled")
        self.partial_path = partial_path


def partial_path_for(destination: Path) -> Path:
    return destination.with_name(destination.name + ".part")


def download_file(
    item: LunaFile,
    destination: Path,
    progress: ProgressCallback | None = None,
    cancel_event: threading.Event | None = None,
    chunk_size: int = 1024 * 256,
) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)

    partial_path = partial_path_for(destination)
    total = item.bytes

    if total is not None and destination.exists() and destination.stat().st_size >= total:
        if progress:
            progress(DownloadProgress(item.name, total, total, 0.0))
        return destination

    if total is not None and destination.exists() and destination.stat().st_size < total:
        if partial_path.exists():
            partial_path.unlink()
        destination.replace(partial_path)

    existing = partial_path.stat().st_size if partial_path.exists() else 0
    if total is not None and existing >= total:
        partial_path.replace(destination)
        if progress:
            progress(DownloadProgress(item.name, total, total, 0.0))
        return destination

    headers = {"User-Agent": "Insta360 Luna Downloader/0.1", "Accept-Encoding": "identity"}
    if existing > 0:
        headers["Range"] = f"bytes={existing}-"

    request = Request(item.url, headers=headers)
    try:
        response = urlopen(request, timeout=10)
    except HTTPError as exc:
        if existing > 0 and exc.code == 416:
            if total is not None and existing >= total:
                partial_path.replace(destination)
                return destination
            partial_path.unlink(missing_ok=True)
            existing = 0
            request = Request(item.url, headers={"User-Agent": "Insta360 Luna Downloader/0.1"})
            response = urlopen(request, timeout=10)
        else:
            raise

    status = getattr(response, "status", response.getcode())
    if existing > 0 and status == 200:
        partial_path.unlink(missing_ok=True)
        existing = 0
    elif existing > 0 and status != 206:
        response.close()
        raise OSError(f"Unexpected HTTP status {status} while resuming {item.name}")

    if progress and existing > 0:
        progress(DownloadProgress(item.name, existing, total, 0.0))

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
                total,
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
                emit_progress(force=total is not None and downloaded >= total)

                if total is not None and downloaded >= total:
                    break
    except DownloadCancelled:
        raise

    if total is not None and downloaded < total:
        raise OSError(f"Incomplete download for {item.name}: {downloaded}/{total} bytes")

    emit_progress(force=True)
    partial_path.replace(destination)
    return destination
