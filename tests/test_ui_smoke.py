import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QTableWidget

from luna_downloader.models import DownloadProgress
from luna_downloader.ui.main_window import MainWindow


def test_main_window_contains_required_controls():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    assert "未连接" in window.connection_label.text()
    assert window.refresh_button.text() == "刷新文件"
    assert window.download_button.text() == "开始下载"
    assert window.choose_folder_button.text() == "选择文件夹"
    assert isinstance(window.file_table, QTableWidget)
    assert window.file_table.columnCount() == 6
    assert app is not None


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
