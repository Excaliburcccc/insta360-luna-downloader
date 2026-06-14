from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from .downloader import DownloadCancelled, download_file
from .luna_client import DEFAULT_HOST, LunaClient, LunaConnectionKeeper
from .models import DownloadProgress, LunaFile


class FileListWorker(QObject):
    finished = Signal(list)
    failed = Signal(str)
    status = Signal(str)

    def __init__(self, host: str = DEFAULT_HOST):
        super().__init__()
        self.host = host

    @Slot()
    def run(self) -> None:
        client = LunaClient(self.host)
        try:
            self.status.emit("正在打开 Luna 授权会话...")
            client.connect()
            self.status.emit("正在读取相机文件列表...")
            self.finished.emit(client.list_files())
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            client.close()


class ConnectionWorker(QObject):
    connected = Signal(list)
    disconnected = Signal(str)
    status = Signal(str)

    def __init__(self, host: str = DEFAULT_HOST, interval: float = 5.0):
        super().__init__()
        self.host = host
        self.interval = interval
        self.stop_event = threading.Event()

    def stop(self) -> None:
        self.stop_event.set()

    @Slot()
    def run(self) -> None:
        client = LunaClient(self.host)
        try:
            try:
                self.status.emit("正在打开 Luna 授权会话...")
                client.connect()
                self.status.emit("正在读取相机文件列表...")
                self.connected.emit(client.list_files())
            except Exception as exc:
                self.disconnected.emit(str(exc))
                return

            while not self.stop_event.wait(self.interval):
                try:
                    client.connect()
                    client.list_files()
                except Exception as exc:
                    self.disconnected.emit(str(exc))
                    return
        finally:
            client.close()


class DownloadWorker(QObject):
    progress = Signal(object)
    file_started = Signal(str)
    file_finished = Signal(str)
    cancelled = Signal(str)
    finished = Signal()
    failed = Signal(str)
    status = Signal(str)

    def __init__(self, files: list[LunaFile], out_dir: Path, host: str = DEFAULT_HOST):
        super().__init__()
        self.files = files
        self.out_dir = out_dir
        self.host = host
        self.cancel_event = threading.Event()

    def cancel(self) -> None:
        self.cancel_event.set()

    @Slot()
    def run(self) -> None:
        client = LunaClient(self.host)
        keeper = LunaConnectionKeeper(client)
        try:
            self.status.emit("正在打开 Luna 授权会话...")
            client.connect()
            keeper.start()
            for item in self.files:
                if self.cancel_event.is_set():
                    self.status.emit("下载已取消。")
                    self.cancelled.emit(item.name)
                    break
                self.file_started.emit(item.name)
                destination = self.out_dir / item.name
                try:
                    client.connect()
                    download_file(item, destination, self.progress.emit, self.cancel_event)
                except DownloadCancelled:
                    self.status.emit("下载已取消，可稍后继续。")
                    self.cancelled.emit(item.name)
                    break
                self.file_finished.emit(item.name)
            self.finished.emit()
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            keeper.stop()
            client.close()
