from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Qt
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..luna_client import DEFAULT_HOST
from ..models import DownloadProgress, LunaFile
from ..workers import ConnectionWorker, DownloadWorker, FileListWorker

PROGRESS_SCALE = 10_000


def format_bytes(value: int | None) -> str:
    if value is None:
        return "未知"
    units = ["B", "KB", "MB", "GB", "TB"]
    amount = float(value)
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(amount):,} {unit}"
            return f"{amount:.2f} {unit}"
        amount /= 1024


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Insta360 Luna 下载器")
        self.resize(980, 680)

        self.files: list[LunaFile] = []
        self.connection_thread: QThread | None = None
        self.connection_worker: ConnectionWorker | None = None
        self.download_thread: QThread | None = None
        self.download_worker: DownloadWorker | None = None
        self.worker_thread: QThread | None = None
        self.active_worker = None
        self.completed_files = 0
        self.download_cancelled = False

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        connection_row = QHBoxLayout()
        self.connection_indicator = QLabel("●")
        self.connection_indicator.setFixedWidth(18)
        self.connection_label = QLabel("未连接 - 请先让电脑连接 Luna Wi-Fi，然后点击连接")
        self.connection_label.setStyleSheet("font-weight: 600;")
        self.host_input = QLineEdit(DEFAULT_HOST)
        self.host_input.setFixedWidth(140)
        self.refresh_button = QPushButton("连接")
        connection_row.addWidget(QLabel("相机 IP:"))
        connection_row.addWidget(self.host_input)
        connection_row.addWidget(self.connection_indicator)
        connection_row.addWidget(self.connection_label, 1)
        connection_row.addWidget(self.refresh_button)
        layout.addLayout(connection_row)
        self.set_connection_state("disconnected", self.connection_label.text())

        filter_row = QHBoxLayout()
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["全部文件", "仅 MP4", "仅 LRV"])
        self.select_all_checkbox = QCheckBox("全选当前列表")
        filter_row.addWidget(QLabel("筛选:"))
        filter_row.addWidget(self.filter_combo)
        filter_row.addWidget(self.select_all_checkbox)
        filter_row.addStretch(1)
        layout.addLayout(filter_row)

        self.file_table = QTableWidget(0, 6)
        self.file_table.setHorizontalHeaderLabels(
            ["选择", "文件名", "类型", "日期", "大小", "状态"]
        )
        self.file_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.file_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.file_table.horizontalHeader().setStretchLastSection(True)
        self.file_table.setColumnWidth(0, 70)
        self.file_table.setColumnWidth(1, 330)
        self.file_table.setColumnWidth(2, 80)
        self.file_table.setColumnWidth(3, 145)
        self.file_table.setColumnWidth(4, 90)
        layout.addWidget(self.file_table, 1)

        path_row = QHBoxLayout()
        self.download_path = QLineEdit(str(Path.cwd() / "downloads"))
        self.choose_folder_button = QPushButton("选择文件夹")
        path_row.addWidget(QLabel("下载到:"))
        path_row.addWidget(self.download_path, 1)
        path_row.addWidget(self.choose_folder_button)
        layout.addLayout(path_row)

        action_row = QHBoxLayout()
        self.download_button = QPushButton("开始下载")
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setEnabled(False)
        action_row.addWidget(self.download_button)
        action_row.addWidget(self.cancel_button)
        action_row.addStretch(1)
        layout.addLayout(action_row)

        self.current_file_label = QLabel("空闲")
        self.file_progress = QProgressBar()
        self.file_progress.setRange(0, PROGRESS_SCALE)
        self.total_progress = QProgressBar()
        layout.addWidget(self.current_file_label)
        layout.addWidget(self.file_progress)
        layout.addWidget(self.total_progress)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(500)
        layout.addWidget(self.log)

        self.refresh_button.clicked.connect(self.connect_to_luna)
        self.choose_folder_button.clicked.connect(self.choose_download_folder)
        self.download_button.clicked.connect(self.start_download)
        self.cancel_button.clicked.connect(self.cancel_download)
        self.filter_combo.currentIndexChanged.connect(self.populate_table)
        self.select_all_checkbox.stateChanged.connect(self.set_visible_selection)

    def log_message(self, message: str) -> None:
        self.log.appendPlainText(message)

    def host(self) -> str:
        return self.host_input.text().strip() or DEFAULT_HOST

    def set_connection_state(self, state: str, message: str) -> None:
        colors = {
            "connected": "#15803d",
            "connecting": "#ca8a04",
            "disconnected": "#b91c1c",
        }
        color = colors.get(state, colors["disconnected"])
        self.connection_indicator.setStyleSheet(f"color: {color}; font-size: 18px; font-weight: 700;")
        self.connection_label.setText(message)

    def connect_to_luna(self) -> None:
        if self.connection_thread is not None:
            return
        self.set_connection_state("connecting", "正在连接 Luna...")
        self.refresh_button.setText("连接中...")
        self.refresh_button.setEnabled(False)

        worker = ConnectionWorker(self.host())
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.status.connect(self.log_message)
        worker.connected.connect(self.on_connection_files_loaded)
        worker.disconnected.connect(self.on_connection_disconnected)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(self.clear_connection_worker)
        self.connection_thread = thread
        self.connection_worker = worker
        thread.start()

    def refresh_files(self) -> None:
        self.connect_to_luna()

    def legacy_refresh_files(self) -> None:
        if self.worker_thread is not None:
            return
        self.set_busy(True)
        self.connection_label.setText("正在连接...")
        worker = FileListWorker(self.host())
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.status.connect(self.log_message)
        worker.finished.connect(self.on_files_loaded)
        worker.failed.connect(self.on_worker_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(self.clear_worker)
        self.worker_thread = thread
        self.active_worker = worker
        thread.start()

    def on_connection_files_loaded(self, files: list[LunaFile]) -> None:
        self.files = files
        self.set_connection_state("connected", f"已连接 - 共 {len(files)} 个文件")
        self.refresh_button.setText("已连接")
        self.refresh_button.setEnabled(False)
        self.log_message(f"已从 Luna 读取 {len(files)} 个文件。")
        self.populate_table()
        self.set_busy(False)

    def on_connection_disconnected(self, message: str) -> None:
        self.set_connection_state("connecting", "连接断开，正在自动重试...")
        self.log_message(f"连接保持失败，正在重试：{message}")

    def clear_connection_worker(self) -> None:
        self.connection_thread = None
        self.connection_worker = None
        self.refresh_button.setText("连接")
        self.refresh_button.setEnabled(True)

    def on_files_loaded(self, files: list[LunaFile]) -> None:
        self.files = files
        self.connection_label.setText(f"已连接 - 共 {len(files)} 个文件")
        self.log_message(f"已从 Luna 读取 {len(files)} 个文件。")
        self.populate_table()
        self.set_busy(False)

    def on_worker_failed(self, message: str) -> None:
        self.connection_label.setText("未连接或未授权")
        self.log_message(f"错误：{message}")
        self.set_busy(False)
        QMessageBox.warning(self, "Luna 下载器", message)

    def clear_worker(self) -> None:
        self.worker_thread = None
        self.active_worker = None

    def clear_download_worker(self) -> None:
        self.download_thread = None
        self.download_worker = None
        self.active_worker = None

    def set_busy(self, busy: bool) -> None:
        self.refresh_button.setEnabled(not busy and self.connection_thread is None)
        self.download_button.setEnabled(not busy and self.file_table.rowCount() > 0)

    def visible_files(self) -> list[LunaFile]:
        mode = self.filter_combo.currentText()
        if mode == "仅 MP4":
            return [item for item in self.files if item.kind == "MP4"]
        if mode == "仅 LRV":
            return [item for item in self.files if item.kind == "LRV"]
        return list(self.files)

    def populate_table(self) -> None:
        visible = self.visible_files()
        self.file_table.setRowCount(len(visible))
        for row, item in enumerate(visible):
            check = QTableWidgetItem("")
            check.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            check.setCheckState(Qt.CheckState.Unchecked)
            check.setData(Qt.ItemDataRole.UserRole, item)
            self.file_table.setItem(row, 0, check)
            self.file_table.setItem(row, 1, QTableWidgetItem(item.name))
            self.file_table.setItem(row, 2, QTableWidgetItem(item.kind))
            self.file_table.setItem(row, 3, QTableWidgetItem(f"{item.date} {item.time}"))
            self.file_table.setItem(row, 4, QTableWidgetItem(item.size_text))
            self.file_table.setItem(row, 5, QTableWidgetItem(self.file_status(item)))
        self.download_button.setEnabled(self.file_table.rowCount() > 0)

    def download_destination(self, item: LunaFile) -> Path:
        return Path(self.download_path.text()).expanduser() / item.name

    def file_status(self, item: LunaFile) -> str:
        destination = self.download_destination(item)
        if destination.exists():
            return "完成"
        if destination.with_name(destination.name + ".part").exists():
            return "可继续"
        return "就绪"

    def is_download_complete(self, item: LunaFile) -> bool:
        return self.download_destination(item).exists()

    def set_visible_selection(self, state: int) -> None:
        checked = Qt.CheckState.Checked if state else Qt.CheckState.Unchecked
        for row in range(self.file_table.rowCount()):
            item = self.file_table.item(row, 0)
            if item is not None:
                item.setCheckState(checked)

    def choose_download_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择下载文件夹", self.download_path.text())
        if folder:
            self.download_path.setText(folder)

    def selected_files(self) -> list[LunaFile]:
        selected: list[LunaFile] = []
        for row in range(self.file_table.rowCount()):
            item = self.file_table.item(row, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                luna_file = item.data(Qt.ItemDataRole.UserRole)
                if not self.is_download_complete(luna_file):
                    selected.append(luna_file)
        return selected

    def start_download(self) -> None:
        if self.download_thread is not None:
            return
        files = self.selected_files()
        if not files:
            QMessageBox.information(self, "Luna 下载器", "请至少选择一个未完成的文件。")
            return
        out_dir = Path(self.download_path.text()).expanduser()
        self.completed_files = 0
        self.download_cancelled = False
        self.total_progress.setMaximum(len(files))
        self.total_progress.setValue(0)
        self.file_progress.setRange(0, PROGRESS_SCALE)
        self.file_progress.setValue(0)
        self.cancel_button.setEnabled(True)
        self.download_button.setEnabled(False)
        self.refresh_button.setEnabled(False)

        worker = DownloadWorker(files, out_dir, self.host())
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.status.connect(self.log_message)
        worker.file_started.connect(self.on_file_started)
        worker.progress.connect(self.on_download_progress)
        worker.file_finished.connect(self.on_file_finished)
        worker.cancelled.connect(self.on_download_cancelled)
        worker.failed.connect(self.on_download_failed)
        worker.finished.connect(self.on_download_finished)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(self.clear_download_worker)
        self.download_thread = thread
        self.download_worker = worker
        self.active_worker = worker
        thread.start()

    def cancel_download(self) -> None:
        if self.active_worker and hasattr(self.active_worker, "cancel"):
            self.active_worker.cancel()
            self.log_message("正在取消下载...")

    def on_file_started(self, name: str) -> None:
        self.current_file_label.setText(f"正在下载 {name}")
        self.file_progress.setRange(0, PROGRESS_SCALE)
        self.file_progress.setValue(0)
        self.update_file_status(name, "下载中")

    def on_download_progress(self, progress: DownloadProgress) -> None:
        if progress.total:
            percent = min(100.0, (progress.downloaded / progress.total) * 100)
            scaled_value = min(PROGRESS_SCALE, int(progress.downloaded * PROGRESS_SCALE / progress.total))
            self.file_progress.setRange(0, PROGRESS_SCALE)
            self.file_progress.setValue(scaled_value)
            total_text = format_bytes(progress.total)
        else:
            percent = 0.0
            self.file_progress.setRange(0, PROGRESS_SCALE)
            total_text = "未知"
        speed = progress.speed_bps / (1024 * 1024)
        self.current_file_label.setText(
            f"{progress.file_name} - {format_bytes(progress.downloaded)} / {total_text} - "
            f"{percent:.2f}% - {speed:.1f} MB/s"
        )

    def on_file_finished(self, name: str) -> None:
        self.completed_files += 1
        self.total_progress.setValue(self.completed_files)
        self.file_progress.setValue(PROGRESS_SCALE)
        self.update_file_status(name, "完成")

    def on_download_cancelled(self, name: str) -> None:
        self.download_cancelled = True
        self.current_file_label.setText("下载已取消，可继续")
        self.update_file_status(name, "已取消，可继续")

    def on_download_finished(self) -> None:
        if self.download_cancelled:
            self.current_file_label.setText("下载已取消，可继续")
            self.log_message("下载已取消，可稍后继续。")
        else:
            self.current_file_label.setText("下载完成")
            self.log_message("下载完成。")
        self.cancel_button.setEnabled(False)
        self.download_button.setEnabled(True)
        self.refresh_button.setEnabled(self.connection_thread is None)

    def on_download_failed(self, message: str) -> None:
        self.log_message(f"错误：{message}")
        self.cancel_button.setEnabled(False)
        self.download_button.setEnabled(True)
        self.refresh_button.setEnabled(self.connection_thread is None)
        QMessageBox.warning(self, "Luna 下载器", message)

    def update_file_status(self, name: str, status: str) -> None:
        for row in range(self.file_table.rowCount()):
            if self.file_table.item(row, 1).text() == name:
                self.file_table.item(row, 5).setText(status)
                break

    def closeEvent(self, event) -> None:
        if self.download_worker is not None:
            self.download_worker.cancel()
        if self.connection_worker is not None:
            self.connection_worker.stop()
        super().closeEvent(event)


def run_app() -> int:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    return app.exec()
