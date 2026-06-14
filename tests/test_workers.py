from pathlib import Path

import luna_downloader.workers as workers
from luna_downloader.downloader import DownloadCancelled
from luna_downloader.models import LunaFile
from luna_downloader.workers import DownloadWorker


class FakeClient:
    def __init__(self, _host: str):
        self.connected = False

    def connect(self):
        self.connected = True

    def close(self):
        self.connected = False


def make_item() -> LunaFile:
    return LunaFile(
        name="sample.mp4",
        href="sample.mp4",
        url="http://127.0.0.1/sample.mp4",
        date="14-Jun-2026",
        time="12:13",
        size_text="16",
        bytes=16,
        kind="MP4",
    )


def test_download_worker_emits_cancelled_instead_of_file_finished(monkeypatch, tmp_path: Path):
    item = make_item()

    def fake_download_file(_item, destination, _progress, _cancel_event):
        raise DownloadCancelled(destination)

    monkeypatch.setattr(workers, "LunaClient", FakeClient)
    monkeypatch.setattr(workers, "download_file", fake_download_file)

    worker = DownloadWorker([item], tmp_path, "127.0.0.1")
    cancelled = []
    file_finished = []
    finished = []
    failed = []

    worker.cancelled.connect(cancelled.append)
    worker.file_finished.connect(file_finished.append)
    worker.finished.connect(lambda: finished.append(True))
    worker.failed.connect(failed.append)

    worker.run()

    assert cancelled == [item.name]
    assert file_finished == []
    assert failed == []
    assert finished == [True]


def test_download_worker_emits_cancelled_when_cancelled_before_first_file(monkeypatch, tmp_path: Path):
    item = make_item()

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("download_file should not be called after cancellation")

    monkeypatch.setattr(workers, "LunaClient", FakeClient)
    monkeypatch.setattr(workers, "download_file", fail_if_called)

    worker = DownloadWorker([item], tmp_path, "127.0.0.1")
    worker.cancel()
    cancelled = []
    file_finished = []
    finished = []
    failed = []

    worker.cancelled.connect(cancelled.append)
    worker.file_finished.connect(file_finished.append)
    worker.finished.connect(lambda: finished.append(True))
    worker.failed.connect(failed.append)

    worker.run()

    assert cancelled == [item.name]
    assert file_finished == []
    assert failed == []
    assert finished == [True]
