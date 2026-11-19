"""Main application window and its controls."""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QComboBox,
    QColorDialog,
    QAbstractSpinBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.presentation.preview_pane import PreviewPane
from src.services.equal_luminance_color_generator import EqualLuminanceColorGenerator
from src.services.word_document_service import WordDocumentService


class RangeSlider(QWidget):
    """Two-handle slider that always keeps its values in ascending order."""

    minimumChanged = Signal(int)
    maximumChanged = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.minimum_value = 75
        self.maximum_value = 125
        self._active_handle = "minimum"
        self.setMinimumHeight(26)

    def _x(self, value: int) -> float:
        return 8 + (value - 50) * max(1, self.width() - 16) / 100

    def _value(self, x: float) -> int:
        return max(50, min(150, round(50 + (x - 8) * 100 / max(1, self.width() - 16))))

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = self.height() / 2
        left, right = self._x(self.minimum_value), self._x(self.maximum_value)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#d9dde4"))
        painter.drawRoundedRect(8, int(center - 2), self.width() - 16, 5, 2, 2)
        painter.setPen(QPen(QColor("#8b929e"), 1))
        for tick in range(11):
            x = 8 + tick * max(1, self.width() - 16) / 10
            painter.drawLine(int(x), int(center + 4), int(x), int(center + 9))
        for tick in range(10):
            x = 8 + (tick + 0.5) * max(1, self.width() - 16) / 10
            painter.drawLine(int(x), int(center + 4), int(x), int(center + 7))
        painter.setBrush(QColor("#5877d8"))
        painter.drawRoundedRect(int(left), int(center - 2), max(1, int(right - left)), 5, 2, 2)
        painter.drawEllipse(int(left - 8), int(center - 8), 16, 16)
        painter.drawEllipse(int(right - 8), int(center - 8), 16, 16)

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        x = event.position().x()
        self._active_handle = "minimum" if abs(x - self._x(self.minimum_value)) <= abs(x - self._x(self.maximum_value)) else "maximum"
        self._move_handle(x)

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._move_handle(event.position().x())

    def _move_handle(self, x: float) -> None:
        value = self._value(x)
        if self._active_handle == "minimum":
            if value <= self.maximum_value:
                self.minimum_value = value
                self.minimumChanged.emit(value)
            else:
                self.minimum_value, self.maximum_value = self.maximum_value, value
                self._active_handle = "maximum"
                self.minimumChanged.emit(self.minimum_value)
                self.maximumChanged.emit(self.maximum_value)
        elif value >= self.minimum_value:
            self.maximum_value = value
            self.maximumChanged.emit(value)
        else:
            self.minimum_value, self.maximum_value = value, self.minimum_value
            self._active_handle = "minimum"
            self.minimumChanged.emit(self.minimum_value)
            self.maximumChanged.emit(self.maximum_value)
        self.update()


class MainWindow(QMainWindow):
    """Main form for document selection, appearance settings and previews."""

    RECOMMENDED_TEXT_COLOR = "#515100"
    RECOMMENDED_BACKGROUND_COLOR = "#8f00ff"

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("OcrDisturber")
        self.setFixedSize(1450, 894)
        self._warning_height_with_spacing = 56
        self._warning_is_visible = False
        self.loaded_file_data: bytes | None = None
        self.loaded_file_path: Path | None = None
        self.document_paragraphs: list[str] = []
        self.document_service = WordDocumentService()
        self.equal_luminance_color_generator = EqualLuminanceColorGenerator()
        # Same Rec. 601 grayscale value, with a dark text color and a vivid,
        # clearly different background hue.
        self.text_color = QColor(self.RECOMMENDED_TEXT_COLOR)
        self.background_color = QColor(self.RECOMMENDED_BACKGROUND_COLOR)

        content = QWidget(self)
        self.setCentralWidget(content)
        root = QVBoxLayout(content)
        root.setContentsMargins(26, 26, 26, 26)
        root.setSpacing(16)

        self.preview_warning = QFrame()
        self.preview_warning.setObjectName("previewWarningBanner")
        self.preview_warning.setFixedHeight(40)
        warning_layout = QHBoxLayout(self.preview_warning)
        warning_layout.setContentsMargins(12, 2, 6, 2)
        warning_layout.setSpacing(8)
        warning_text = QLabel(
            "Таблицы, формулы, изображения и прочие специальные символы и рисунки "
            "в предпросмотре могут отображаться некорректно"
        )
        warning_text.setObjectName("previewWarningText")
        warning_layout.addWidget(warning_text, 1)
        warning_close = QPushButton("×")
        warning_close.setObjectName("previewWarningClose")
        warning_close.setFixedSize(28, 28)
        warning_close.setToolTip("Скрыть предупреждение")
        warning_close.clicked.connect(self._dismiss_preview_warning)
        warning_layout.addWidget(warning_close)
        self.preview_warning.hide()
        root.addWidget(self.preview_warning)

        file_panel = QFrame()
        file_panel.setObjectName("filePanel")
        file_layout = QHBoxLayout(file_panel)
        file_layout.setContentsMargins(18, 14, 18, 14)
        file_layout.setSpacing(12)

        self.file_path = QLineEdit()
        self.file_path.setReadOnly(True)
        self.file_path.setPlaceholderText("Выберите документ Word (.docx)")
        self.file_path.setStyleSheet("font-weight: bold;")
        self.file_path.setClearButtonEnabled(False)
        self.file_button = QPushButton("Обзор…")
        self.file_button.clicked.connect(self.choose_word_file)
        file_layout.addWidget(self._label("Выберите файл"))
        file_layout.addWidget(self.file_path, 1)
        file_layout.addWidget(self.file_button)
        root.addWidget(file_panel)

        self.color_preview = PreviewPane(title="Предпросмотр с цветом и заливкой фона")
        self.monochrome_preview = PreviewPane(
            title="Предпросмотр с цветом и заливкой фона + ч/б фильтр",
            monochrome=True,
        )
        preview_row = QHBoxLayout()
        preview_row.setSpacing(18)
        preview_row.addWidget(self.color_preview, 1)
        preview_row.addWidget(self.monochrome_preview, 1)

        self.color_settings_panel = QFrame()
        self.color_settings_panel.setObjectName("colorSettingsPanel")
        self.color_settings_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        color_layout = QVBoxLayout(self.color_settings_panel)
        color_layout.setContentsMargins(14, 12, 14, 12)
        color_layout.setSpacing(10)
        color_title = QLabel("Настройки цвета")
        color_title.setObjectName("panelTitle")
        color_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        color_layout.addWidget(color_title)

        swatch_row = QHBoxLayout()
        swatch_row.setSpacing(12)
        swatch_column = QVBoxLayout()
        swatch_column.setSpacing(6)
        swatch_column.addWidget(self._label("Текст"), alignment=Qt.AlignmentFlag.AlignHCenter)
        self.text_color_swatch = self._color_swatch(self.text_color)
        self.text_color_swatch.clicked.connect(
            lambda: self._choose_swatch_color("text_color", self.text_color_swatch, "Выберите цвет текста")
        )
        swatch_column.addWidget(self.text_color_swatch, alignment=Qt.AlignmentFlag.AlignHCenter)
        swatch_row.addLayout(swatch_column, 1)

        swatch_column = QVBoxLayout()
        swatch_column.setSpacing(6)
        swatch_column.addWidget(self._label("Фон"), alignment=Qt.AlignmentFlag.AlignHCenter)
        self.background_color_swatch = self._color_swatch(self.background_color)
        self.background_color_swatch.clicked.connect(
            lambda: self._choose_swatch_color("background_color", self.background_color_swatch, "Выберите цвет фона")
        )
        swatch_column.addWidget(self.background_color_swatch, alignment=Qt.AlignmentFlag.AlignHCenter)
        swatch_row.addLayout(swatch_column, 1)
        color_layout.addLayout(swatch_row)

        self.find_equal_background_button = QPushButton("Найти равнояркий фон")
        self.find_equal_background_button.clicked.connect(self._find_equal_luminance_background)
        color_layout.addWidget(self.find_equal_background_button)
        self.find_equal_text_button = QPushButton("Найти равнояркий текст")
        self.find_equal_text_button.clicked.connect(self._find_equal_luminance_text)
        color_layout.addWidget(self.find_equal_text_button)
        self.recommended_colors_button = QPushButton("Вернуться к рекомендованным")
        self.recommended_colors_button.clicked.connect(self._restore_recommended_colors)
        color_layout.addWidget(self.recommended_colors_button)

        background_panel = QFrame()
        background_panel.setObjectName("backgroundSettingsPanel")
        background_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        background_layout = QVBoxLayout(background_panel)
        background_layout.setContentsMargins(14, 12, 14, 12)
        background_layout.setSpacing(8)
        background_title = QLabel("Настройки фона")
        background_title.setObjectName("panelTitle")
        background_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        background_layout.addWidget(background_title)

        background_types_frame = QGroupBox("Заполнение")
        background_types_frame.setObjectName("backgroundTypesFrame")
        background_types_layout = QVBoxLayout(background_types_frame)
        background_types_layout.setContentsMargins(12, 12, 12, 12)
        background_types_layout.setSpacing(8)

        self.background_type_selectors: dict[str, QCheckBox] = {}
        for key, title in (
            ("punctuation", "Знаки препинания"),
            ("shapes", "Геометрические фигуры"),
            ("pepper", "Перец"),
        ):
            selector = QCheckBox(title)
            background_types_layout.addWidget(selector)
            self.background_type_selectors[key] = selector
        background_layout.addWidget(background_types_frame)

        self.background_range = RangeSlider()
        self.background_minimum = self.background_range
        self.background_maximum = self.background_range
        background_layout.addWidget(self._label("Размер фона. Коэффициенты к размеру текста"))
        background_layout.addWidget(self.background_range)
        scale_labels = QHBoxLayout()
        for value in ("0.5", "0.75", "1", "1.25", "1.5"):
            scale_labels.addWidget(QLabel(value), alignment=Qt.AlignmentFlag.AlignHCenter)
            if value != "1.5":
                scale_labels.addStretch(1)
        background_layout.addLayout(scale_labels)
        background_layout.addWidget(self._label("Степень заполнения фона"))
        self.background_fill_slider = QSlider(Qt.Orientation.Horizontal)
        self.background_fill_slider.setRange(0, 100)
        self.background_fill_slider.setValue(50)
        self.background_fill_slider.setTickPosition(QSlider.TickPosition.NoTicks)
        background_layout.addWidget(self.background_fill_slider)
        self.download_button = QPushButton("Скачать файл")
        self.download_button.setObjectName("downloadButton")
        self.download_button.setFixedHeight(48)
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(self.download_file)

        self.apply_settings_button = QPushButton("Применить настройки")
        self.apply_settings_button.clicked.connect(self.apply_settings_to_preview)

        page_controls = QWidget()
        page_controls_layout = QVBoxLayout(page_controls)
        page_controls_layout.setContentsMargins(0, 6, 0, 0)
        page_controls_layout.setSpacing(4)
        page_label = QLabel("Страница предпросмотра")
        page_label.setObjectName("fieldLabel")
        page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_selector = QSpinBox()
        self.page_selector.setRange(1, 1)
        self.page_selector.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.page_selector.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_selector.setFixedWidth(64)
        self.page_selector.valueChanged.connect(self._show_preview_page)
        self.previous_page_button = QPushButton("‹")
        self.previous_page_button.setFixedSize(36, 34)
        self.previous_page_button.setStyleSheet("padding: 0; font-size: 20px;")
        self.previous_page_button.clicked.connect(self.page_selector.stepDown)
        self.next_page_button = QPushButton("›")
        self.next_page_button.setFixedSize(36, 34)
        self.next_page_button.setStyleSheet("padding: 0; font-size: 20px;")
        self.next_page_button.clicked.connect(self.page_selector.stepUp)
        page_navigation = QHBoxLayout()
        page_navigation.setSpacing(8)
        page_navigation.addStretch(1)
        page_navigation.addWidget(self.previous_page_button)
        page_navigation.addWidget(self.page_selector)
        page_navigation.addWidget(self.next_page_button)
        page_navigation.addStretch(1)
        page_controls_layout.addWidget(page_label)
        page_controls_layout.addLayout(page_navigation)
        self._update_page_navigation(1)

        right_controls = QVBoxLayout()
        right_controls.setSpacing(12)
        right_controls.addWidget(self.color_settings_panel)
        right_controls.addWidget(background_panel)
        right_controls.addWidget(self.apply_settings_button)
        right_controls.addWidget(page_controls)
        right_controls.addStretch(1)
        right_controls.addWidget(self.download_button)

        work_area = QHBoxLayout()
        work_area.setSpacing(18)
        work_area.addLayout(preview_row, 1)
        work_area.addLayout(right_controls, 0)
        root.addLayout(work_area, 1)

        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #f5f6f8; color: #252a32; }
            #filePanel, #previewPanel, #colorSettingsPanel, #backgroundSettingsPanel {
                background: #ffffff;
                border: 1px solid #d9dde4;
                border-radius: 14px;
            }
            #backgroundTypesFrame {
                background: transparent;
                border: 1px solid #d9dde4;
                border-radius: 10px;
                margin-top: 8px;
                padding-top: 6px;
            }
            QGroupBox#backgroundTypesFrame::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 0 6px;
                background: #ffffff;
                color: #424955;
            }
            QLabel#fieldLabel { color: #424955; font-size: 12px; }
            QLabel#fieldLabel, QCheckBox { background: transparent; }
            QLineEdit, QComboBox {
                background: #ffffff;
                border: 1px solid #c9ced8;
                border-radius: 7px;
                padding: 6px 9px;
                min-height: 16px;
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
            QPushButton#downloadButton { background: #c7d2ee; }
            QPushButton#downloadButton:hover { background: #b4c3e8; }
            QLabel#previewTitle, QLabel#panelTitle {
                background: transparent;
                color: #646c79;
                font-size: 13px;
                font-weight: bold;
            }
            #previewWarningBanner { background: #fff2c6; border: 1px solid #e5c75b; border-radius: 8px; }
            QLabel#previewWarningText { background: transparent; color: #554617; font-size: 12px; }
            QPushButton#previewWarningClose { background: transparent; border: 0; padding: 0px 0px 3px 0px; font-size: 18px; text-align: center; color: #554617; }
            QPushButton#previewWarningClose:hover { background: #f3df9b; border-radius: 4px; }
            #a4Page { background: #ffffff; border: 1px solid #c9ced8; }
            """
        )
        # The initial grayscale snapshot is first rendered during PreviewPane
        # construction, before this stylesheet sets the A4 page background.
        self.monochrome_preview.set_monochrome(True)

    @staticmethod
    def _label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        return label

    @staticmethod
    def _color_swatch(color: QColor) -> QPushButton:
        """Create a clickable color sample."""
        swatch = QPushButton()
        swatch.setFixedSize(62, 34)
        swatch.setStyleSheet(
            f"background-color: {color.name()}; border: 1px solid #c9ced8; border-radius: 3px;"
        )
        return swatch

    def _choose_swatch_color(self, attribute: str, swatch: QPushButton, title: str) -> None:
        """Choose a color and keep it on its sample button."""
        selected = QColorDialog.getColor(getattr(self, attribute), self, title)
        if selected.isValid():
            setattr(self, attribute, selected)
            swatch.setStyleSheet(
                f"background-color: {selected.name()}; border: 1px solid #c9ced8; border-radius: 3px;"
            )

    def _find_equal_luminance_background(self) -> None:
        """Set the background to a color with the text's grayscale value."""
        self._set_swatch_color(
            "background_color",
            self.background_color_swatch,
            self.equal_luminance_color_generator.find_equal_luminance_color(self.text_color),
        )

    def _find_equal_luminance_text(self) -> None:
        """Set the text to a color with the background's grayscale value."""
        self._set_swatch_color(
            "text_color",
            self.text_color_swatch,
            self.equal_luminance_color_generator.find_equal_luminance_color(self.background_color),
        )

    def _restore_recommended_colors(self) -> None:
        """Restore the recommended text and background colors in settings."""
        self._set_swatch_color(
            "text_color", self.text_color_swatch, QColor(self.RECOMMENDED_TEXT_COLOR)
        )
        self._set_swatch_color(
            "background_color",
            self.background_color_swatch,
            QColor(self.RECOMMENDED_BACKGROUND_COLOR),
        )

    def _set_swatch_color(self, attribute: str, swatch: QPushButton, color: QColor) -> None:
        """Update a selected color and its visible sample."""
        setattr(self, attribute, color)
        swatch.setStyleSheet(
            f"background-color: {color.name()}; border: 1px solid #c9ced8; border-radius: 3px;"
        )

    def show(self) -> None:
        """Display the main window."""
        super().show()

    def choose_word_file(self) -> None:
        """Open a file picker filtered to .docx files."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите документ Word (.docx)",
            "",
            "Документы Word (*.docx)",
        )
        if file_path:
            try:
                data, paragraphs = self.document_service.read(file_path)
            except (OSError, ValueError) as error:
                QMessageBox.critical(self, "Не удалось загрузить документ", str(error))
                return
            self.file_path.setText(file_path)
            self.loaded_file_data = data
            self.loaded_file_path = Path(file_path)
            self.document_paragraphs = paragraphs
            self.color_preview.set_text_color(None)
            self.monochrome_preview.set_text_color(None)
            self.color_preview.set_background_color(None)
            self.monochrome_preview.set_background_color(None)
            self.color_preview.set_document_paragraphs(paragraphs)
            self.monochrome_preview.set_document_paragraphs(paragraphs)
            page_count = max(self.color_preview.page_count, self.monochrome_preview.page_count, 1)
            self.page_selector.blockSignals(True)
            self.page_selector.setRange(1, page_count)
            self.page_selector.setValue(1)
            self.page_selector.blockSignals(False)
            self._show_preview_page(1)
            self._update_page_navigation(1)
            self.download_button.setEnabled(True)
            self._show_preview_warning()

    def _show_preview_warning(self) -> None:
        """Show the preview caveat and preserve the preview page size."""
        if self._warning_is_visible:
            return
        self._warning_is_visible = True
        self.preview_warning.show()
        self.setFixedSize(self.width(), self.height() + self._warning_height_with_spacing)

    def _dismiss_preview_warning(self) -> None:
        """Hide the preview caveat and restore the compact window height."""
        if not self._warning_is_visible:
            return
        self._warning_is_visible = False
        self.preview_warning.hide()
        self.setFixedSize(self.width(), self.height() - self._warning_height_with_spacing)

    def _show_preview_page(self, page_number: int) -> None:
        """Show the selected page in both preview panes."""
        self.color_preview.show_page(page_number)
        self.monochrome_preview.show_page(page_number)
        self._update_page_navigation(page_number)

    def _update_page_navigation(self, page_number: int) -> None:
        """Enable previous and next buttons when their page exists."""
        self.previous_page_button.setEnabled(page_number > self.page_selector.minimum())
        self.next_page_button.setEnabled(page_number < self.page_selector.maximum())

    def update_previews(self) -> None:
        """Reserved for preview updates when document processing is implemented."""

    def apply_settings_to_preview(self) -> None:
        """Apply the selected text color to both document previews."""
        self.color_preview.set_text_color(self.text_color)
        self.monochrome_preview.set_text_color(self.text_color)
        self.color_preview.set_background_color(self.background_color)
        self.monochrome_preview.set_background_color(self.background_color)

    def download_file(self) -> None:
        """Save the loaded DOCX bytes to a user-selected location."""
        if self.loaded_file_data is None or self.loaded_file_path is None:
            return

        warning = QMessageBox(self)
        warning.setIcon(QMessageBox.Icon.Warning)
        warning.setWindowTitle("Перед скачиванием")
        warning.setText(
            "Созданный файл возможно корректно читать ТОЛЬКО в цветном формате. "
            "При черно-белом фильтре или печати чтение текста будет затруднено "
            "или невозможно."
        )
        download_button = warning.addButton(
            "Понимаю, скачать", QMessageBox.ButtonRole.AcceptRole
        )
        cancel_button = warning.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
        warning.setDefaultButton(cancel_button)
        warning.exec()
        if warning.clickedButton() is not download_button:
            return

        output_name = f"{self.loaded_file_path.stem}_disturbed.docx"
        default_path = str(Path.home() / output_name)
        destination, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить документ Word",
            default_path,
            "Документы Word (*.docx)",
        )
        if not destination:
            return

        destination_path = Path(destination)
        if destination_path.suffix.lower() != ".docx":
            destination_path = destination_path.with_suffix(".docx")
        try:
            processed_data = self.document_service.apply_appearance(
                self.loaded_file_data, self.text_color.name(), self.background_color.name()
            )
            destination_path.write_bytes(processed_data)
        except (OSError, ValueError) as error:
            QMessageBox.critical(
                self,
                "Не удалось сохранить файл",
                f"Не удалось сохранить документ:\n{error}",
            )
            return

        QMessageBox.information(
            self,
            "Файл сохранён",
            f"Файл сохранён в:\n{destination_path}",
        )
