from pathlib import Path
import threading

import luna_downloader.workers as workers
from luna_downloader.downloader import DownloadCancelled
from luna_downloader.models import LunaFile
from luna_downloader.workers import ConnectionWorker, DownloadWorker


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


def make_items(count: int) -> list[LunaFile]:
    items = []
    for index in range(count):
        name = f"sample-{index}.mp4"
        items.append(
            LunaFile(
                name=name,
                href=name,
                url=f"http://127.0.0.1/{name}",
                date="14-Jun-2026",
                time="12:13",
                size_text="16",
                bytes=16,
                kind="MP4",
            )
        )
    return items


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


def test_download_worker_keeps_auth_alive_and_reauths_before_each_file(monkeypatch, tmp_path: Path):
    clients = []
    keepers = []
    downloaded = []

    class CountingClient:
        def __init__(self, _host: str):
            self.connect_count = 0
            self.close_count = 0
            clients.append(self)

        def connect(self):
            self.connect_count += 1

        def close(self):
            self.close_count += 1

    class FakeKeeper:
        def __init__(self, client, interval=20.0):
            self.client = client
            self.interval = interval
            self.start_count = 0
            self.stop_count = 0
            keepers.append(self)

        def start(self):
            self.start_count += 1

        def stop(self):
            self.stop_count += 1

    def fake_download_file(item, destination, _progress, _cancel_event):
        downloaded.append((item.name, destination.name))

    monkeypatch.setattr(workers, "LunaClient", CountingClient)
    monkeypatch.setattr(workers, "LunaConnectionKeeper", FakeKeeper)
    monkeypatch.setattr(workers, "download_file", fake_download_file)

    worker = DownloadWorker(make_items(2), tmp_path, "127.0.0.1")
    worker.run()

    assert [name for name, _dest in downloaded] == ["sample-0.mp4", "sample-1.mp4"]
    assert clients[0].connect_count == 3
    assert clients[0].close_count == 1
    assert keepers[0].start_count == 1
    assert keepers[0].stop_count == 1


def test_connection_worker_stops_after_disconnect(monkeypatch):
    clients = []

    class FlakyClient:
        def __init__(self, _host: str):
            self.connect_count = 0
            self.close_count = 0
            clients.append(self)

        def connect(self):
            self.connect_count += 1
            if self.connect_count > 1:
                raise OSError("network lost")

        def list_files(self):
            return [make_item()]

        def close(self):
            self.close_count += 1

    monkeypatch.setattr(workers, "LunaClient", FlakyClient)
    worker = ConnectionWorker("127.0.0.1", interval=0.001)

    thread = threading.Thread(target=worker.run)
    thread.start()
    thread.join(timeout=0.2)
    still_running = thread.is_alive()
    if still_running:
        worker.stop()
        thread.join(timeout=1)

    assert not still_running
    assert clients[0].connect_count == 2
    assert clients[0].close_count == 1
