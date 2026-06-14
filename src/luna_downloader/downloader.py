from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .models import DownloadProgress, LunaFile

ProgressCallback = Callable[[DownloadProgress], None]


def download_file(
    item: LunaFile,
    destination: Path,
    progress: ProgressCallback | None = None,
    cancel_event: threading.Event | None = None,
    chunk_size: int = 1024 * 256,
) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)

    existing = destination.stat().st_size if destination.exists() else 0
    total = item.bytes
    if total is not None and existing >= total:
        if progress:
            progress(DownloadProgress(item.name, existing, total, 0.0))
        return destination

    headers = {"User-Agent": "Insta360 Luna Downloader/0.1"}
    if existing > 0:
        headers["Range"] = f"bytes={existing}-"

    request = Request(item.url, headers=headers)
    try:
        response = urlopen(request, timeout=10)
    except HTTPError as exc:
        if existing > 0 and exc.code == 416:
            return destination
        raise

    mode = "ab" if existing > 0 else "wb"
    downloaded = existing
    started_at = time.monotonic()
    with response, destination.open(mode + "") as output:
        while True:
            if cancel_event is not None and cancel_event.is_set():
                break

            chunk = response.read(chunk_size)
            if not chunk:
                break

            output.write(chunk)
            downloaded += len(chunk)
            elapsed = max(time.monotonic() - started_at, 0.001)
            if progress:
                progress(
                    DownloadProgress(
                        item.name,
                        downloaded,
                        total,
                        (downloaded - existing) / elapsed,
                    )
                )

    return destination
