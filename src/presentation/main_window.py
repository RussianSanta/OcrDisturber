"""Main application window and its controls."""

import shutil
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.presentation.preview_pane import PreviewPane


class MainWindow(QMainWindow):
    """Main form for document selection, appearance settings and previews."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("OcrDisturber")
        self.setMinimumSize(760, 560)
        self.resize(960, 700)

        content = QWidget(self)
        self.setCentralWidget(content)
        root = QVBoxLayout(content)
        root.setContentsMargins(30, 28, 30, 30)
        root.setSpacing(24)

        settings = QFrame()
        settings.setObjectName("settingsPanel")
        settings_layout = QVBoxLayout(settings)
        settings_layout.setContentsMargins(24, 22, 24, 22)
        settings_layout.setSpacing(14)

        self.file_path = QLineEdit()
        self.file_path.setReadOnly(True)
        self.file_path.setPlaceholderText("Выберите файл Word")
        self.file_path.setClearButtonEnabled(False)
        self.file_button = QPushButton("Обзор…")
        self.file_button.clicked.connect(self.choose_word_file)
        file_row = QHBoxLayout()
        file_row.setSpacing(12)
        file_row.addWidget(self._label("Файл"), 0)
        file_row.addWidget(self.file_path, 1)
        file_row.addWidget(self.file_button)
        settings_layout.addLayout(file_row)

        self.color_pairs = QComboBox()
        self.color_pairs.setPlaceholderText(" ")
        settings_layout.addLayout(self._setting_row("Цветовые пары", self.color_pairs))

        self.background_types = QComboBox()
        self.background_types.setPlaceholderText(" ")
        settings_layout.addLayout(self._setting_row("Тип фона", self.background_types))

        root.addWidget(settings)

        preview_row = QHBoxLayout()
        preview_row.setSpacing(20)
        self.color_preview = PreviewPane(title="Предпросмотр с цветом и заливкой фона")
        self.monochrome_preview = PreviewPane(
            title="Предпросмотр с цветом и заливкой фона + ч/б фильтр",
            monochrome=True,
        )
        preview_row.addWidget(self.color_preview)
        preview_row.addWidget(self.monochrome_preview)
        root.addLayout(preview_row, 1)

        self.download_button = QPushButton("Скачать файл")
        self.download_button.setMinimumWidth(190)
        self.download_button.clicked.connect(self.download_file)
        root.addWidget(self.download_button, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #f5f6f8; color: #252a32; }
            #settingsPanel, #previewPanel {
                background: #ffffff;
                border: 1px solid #d9dde4;
                border-radius: 14px;
            }
            QLabel#fieldLabel { color: #424955; font-size: 14px; }
            QLineEdit, QComboBox {
                background: #ffffff;
                border: 1px solid #c9ced8;
                border-radius: 7px;
                padding: 9px 11px;
                min-height: 20px;
                selection-background-color: #5877d8;
            }
            QComboBox::drop-down { border: 0; width: 28px; }
            QPushButton {
                background: #e9edf8;
                border: 1px solid #d5dcef;
                border-radius: 7px;
                padding: 9px 16px;
            }
            QPushButton:hover { background: #dfe6f7; }
            QLabel#previewTitle { color: #646c79; font-size: 13px; }
            """
        )

    @staticmethod
    def _label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        return label

    @classmethod
    def _setting_row(cls, label_text: str, field: QWidget) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(cls._label(label_text), 0)
        row.addWidget(field, 1)
        return row

    def show(self) -> None:
        """Display the main window."""
        super().show()

    def choose_word_file(self) -> None:
        """Open a file picker filtered to .docx and .doc files."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите документ Word",
            "",
            "Документы Word (*.docx *.doc)",
        )
        if file_path:
            self.file_path.setText(file_path)

    def choose_colors(self) -> None:
        """Reserved for color-pair selection controls."""

    def choose_background_fill(self) -> None:
        """Reserved for background-fill selection controls."""

    def update_previews(self) -> None:
        """Reserved for preview updates when document processing is implemented."""

    def download_file(self) -> None:
        """Confirm the warning and save a copy of the placeholder output."""
        warning = QMessageBox(self)
        warning.setIcon(QMessageBox.Icon.Warning)
        warning.setWindowTitle("Перед скачиванием")
        warning.setText(
            "Созданный файл возможно корректно читать ТОЛЬКО в цветном формате. "
            "При черно белом фильтре или печати чтение текста будет затруднено "
            "или невозможно"
        )
        download_button = warning.addButton(
            "Понимаю, скачать", QMessageBox.ButtonRole.AcceptRole
        )
        cancel_button = warning.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
        warning.setDefaultButton(cancel_button)
        warning.exec()

        if warning.clickedButton() is not download_button:
            return

        default_path = str(Path.home() / "created_file.txt")
        destination, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить созданный файл",
            default_path,
            "Текстовые файлы (*.txt)",
        )
        if not destination:
            return

        source = Path(sys.argv[0]).resolve().parent / "dummy.txt"
        try:
            if source.resolve() != Path(destination).resolve():
                shutil.copyfile(source, destination)
        except OSError as error:
            QMessageBox.critical(
                self,
                "Не удалось сохранить файл",
                f"Не удалось скопировать файл-заглушку:\n{error}",
            )
            return

        QMessageBox.information(
            self,
            "Файл сохранён",
            f"Файл сохранён в:\n{destination}",
        )
