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
from ..workers import DownloadWorker, FileListWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Insta360 Luna Downloader")
        self.resize(980, 680)

        self.files: list[LunaFile] = []
        self.worker_thread: QThread | None = None
        self.active_worker = None
        self.completed_files = 0

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        connection_row = QHBoxLayout()
        self.connection_label = QLabel("Disconnected - connect PC Wi-Fi to Luna, then refresh")
        self.connection_label.setStyleSheet("font-weight: 600;")
        self.host_input = QLineEdit(DEFAULT_HOST)
        self.host_input.setFixedWidth(140)
        self.refresh_button = QPushButton("Refresh files")
        connection_row.addWidget(QLabel("Camera IP:"))
        connection_row.addWidget(self.host_input)
        connection_row.addWidget(self.connection_label, 1)
        connection_row.addWidget(self.refresh_button)
        layout.addLayout(connection_row)

        filter_row = QHBoxLayout()
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All files", "MP4 only", "LRV only"])
        self.select_all_checkbox = QCheckBox("Select all visible")
        filter_row.addWidget(QLabel("Filter:"))
        filter_row.addWidget(self.filter_combo)
        filter_row.addWidget(self.select_all_checkbox)
        filter_row.addStretch(1)
        layout.addLayout(filter_row)

        self.file_table = QTableWidget(0, 6)
        self.file_table.setHorizontalHeaderLabels(
            ["Select", "Name", "Type", "Date", "Size", "Status"]
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
        self.choose_folder_button = QPushButton("Choose folder")
        path_row.addWidget(QLabel("Download to:"))
        path_row.addWidget(self.download_path, 1)
        path_row.addWidget(self.choose_folder_button)
        layout.addLayout(path_row)

        action_row = QHBoxLayout()
        self.download_button = QPushButton("Start download")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        action_row.addWidget(self.download_button)
        action_row.addWidget(self.cancel_button)
        action_row.addStretch(1)
        layout.addLayout(action_row)

        self.current_file_label = QLabel("Idle")
        self.file_progress = QProgressBar()
        self.total_progress = QProgressBar()
        layout.addWidget(self.current_file_label)
        layout.addWidget(self.file_progress)
        layout.addWidget(self.total_progress)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(500)
        layout.addWidget(self.log)

        self.refresh_button.clicked.connect(self.refresh_files)
        self.choose_folder_button.clicked.connect(self.choose_download_folder)
        self.download_button.clicked.connect(self.start_download)
        self.cancel_button.clicked.connect(self.cancel_download)
        self.filter_combo.currentIndexChanged.connect(self.populate_table)
        self.select_all_checkbox.stateChanged.connect(self.set_visible_selection)

    def log_message(self, message: str) -> None:
        self.log.appendPlainText(message)

    def host(self) -> str:
        return self.host_input.text().strip() or DEFAULT_HOST

    def refresh_files(self) -> None:
        if self.worker_thread is not None:
            return
        self.set_busy(True)
        self.connection_label.setText("Connecting...")
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

    def on_files_loaded(self, files: list[LunaFile]) -> None:
        self.files = files
        self.connection_label.setText(f"Connected - {len(files)} files")
        self.log_message(f"Loaded {len(files)} files from Luna.")
        self.populate_table()
        self.set_busy(False)

    def on_worker_failed(self, message: str) -> None:
        self.connection_label.setText("Disconnected or unauthorized")
        self.log_message(f"Error: {message}")
        self.set_busy(False)
        QMessageBox.warning(self, "Luna Downloader", message)

    def clear_worker(self) -> None:
        self.worker_thread = None
        self.active_worker = None

    def set_busy(self, busy: bool) -> None:
        self.refresh_button.setEnabled(not busy)
        self.download_button.setEnabled(not busy and self.file_table.rowCount() > 0)

    def visible_files(self) -> list[LunaFile]:
        mode = self.filter_combo.currentText()
        if mode == "MP4 only":
            return [item for item in self.files if item.kind == "MP4"]
        if mode == "LRV only":
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
            self.file_table.setItem(row, 5, QTableWidgetItem("Ready"))
        self.download_button.setEnabled(self.file_table.rowCount() > 0)

    def set_visible_selection(self, state: int) -> None:
        checked = Qt.CheckState.Checked if state else Qt.CheckState.Unchecked
        for row in range(self.file_table.rowCount()):
            item = self.file_table.item(row, 0)
            if item is not None:
                item.setCheckState(checked)

    def choose_download_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose download folder", self.download_path.text())
        if folder:
            self.download_path.setText(folder)

    def selected_files(self) -> list[LunaFile]:
        selected: list[LunaFile] = []
        for row in range(self.file_table.rowCount()):
            item = self.file_table.item(row, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                selected.append(item.data(Qt.ItemDataRole.UserRole))
        return selected

    def start_download(self) -> None:
        files = self.selected_files()
        if not files:
            QMessageBox.information(self, "Luna Downloader", "Select at least one file to download.")
            return
        out_dir = Path(self.download_path.text()).expanduser()
        self.completed_files = 0
        self.total_progress.setMaximum(len(files))
        self.total_progress.setValue(0)
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
        worker.failed.connect(self.on_worker_failed)
        worker.finished.connect(self.on_download_finished)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(self.clear_worker)
        self.worker_thread = thread
        self.active_worker = worker
        thread.start()

    def cancel_download(self) -> None:
        if self.active_worker and hasattr(self.active_worker, "cancel"):
            self.active_worker.cancel()
            self.log_message("Cancelling download...")

    def on_file_started(self, name: str) -> None:
        self.current_file_label.setText(f"Downloading {name}")
        self.file_progress.setValue(0)
        self.update_file_status(name, "Downloading")

    def on_download_progress(self, progress: DownloadProgress) -> None:
        if progress.total:
            self.file_progress.setMaximum(progress.total)
            self.file_progress.setValue(progress.downloaded)
        speed = progress.speed_bps / (1024 * 1024)
        self.current_file_label.setText(
            f"{progress.file_name} - {progress.downloaded:,}/{progress.total or 0:,} bytes - {speed:.1f} MB/s"
        )

    def on_file_finished(self, name: str) -> None:
        self.completed_files += 1
        self.total_progress.setValue(self.completed_files)
        self.update_file_status(name, "Done")

    def on_download_finished(self) -> None:
        self.current_file_label.setText("Download finished")
        self.log_message("Download finished.")
        self.cancel_button.setEnabled(False)
        self.download_button.setEnabled(True)
        self.refresh_button.setEnabled(True)

    def update_file_status(self, name: str, status: str) -> None:
        for row in range(self.file_table.rowCount()):
            if self.file_table.item(row, 1).text() == name:
                self.file_table.item(row, 5).setText(status)
                break


def run_app() -> int:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    return app.exec()

