import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QTableWidget

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
