import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QTableWidget

from luna_downloader.models import DownloadProgress, LunaFile
from luna_downloader.ui.main_window import MainWindow


def test_main_window_contains_required_controls():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    assert "未连接" in window.connection_label.text()
    assert window.refresh_button.text() == "连接"
    assert window.download_button.text() == "开始下载"
    assert window.choose_folder_button.text() == "选择文件夹"
    assert window.connection_indicator.text() == "●"
    assert isinstance(window.file_table, QTableWidget)
    assert window.file_table.columnCount() == 6
    assert app is not None


def make_item(name: str = "sample.mp4") -> LunaFile:
    return LunaFile(
        name=name,
        href=name,
        url=f"http://127.0.0.1/{name}",
        date="14-Jun-2026",
        time="12:13",
        size_text="16M",
        bytes=16 * 1024 * 1024,
        kind="MP4",
    )


def test_large_download_progress_uses_scaled_progress_bar_values():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    window.on_download_progress(
        DownloadProgress(
            file_name="big.mp4",
            downloaded=3 * 1024**3,
            total=5 * 1024**3,
            speed_bps=32 * 1024**2,
        )
    )

    assert window.file_progress.maximum() == 10_000
    assert window.file_progress.value() == 6_000
    assert "60.00%" in window.current_file_label.text()
    assert app is not None


def test_populate_table_restores_completed_status_from_download_folder(tmp_path: Path):
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    item = make_item()
    (tmp_path / item.name).write_bytes(b"done")

    window.download_path.setText(str(tmp_path))
    window.files = [item]
    window.populate_table()

    assert window.file_table.item(0, 5).text() == "完成"
    assert app is not None


def test_populate_table_restores_partial_status_from_download_folder(tmp_path: Path):
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    item = make_item()
    (tmp_path / f"{item.name}.part").write_bytes(b"partial")

    window.download_path.setText(str(tmp_path))
    window.files = [item]
    window.populate_table()

    assert window.file_table.item(0, 5).text() == "可继续"
    assert app is not None
