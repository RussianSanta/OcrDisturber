"""Word page preview widgets."""

from html import escape

from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap, QTextCharFormat, QTextCursor, QTextDocument
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QTextEdit, QVBoxLayout, QWidget


class BackgroundPatternOverlay(QWidget):
    """Paint a generated background pattern and its temporary zone grid."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._image: QImage | None = None
        self._zones: list[QRectF] = []
        self._show_grid = False

    def set_pattern(
        self,
        image: QImage | None,
        zones: list[QRectF] | None,
        show_grid: bool,
    ) -> None:
        self._image = image
        self._zones = zones or []
        self._show_grid = show_grid
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._image is not None:
            painter.drawImage(self.rect(), self._image)
        if self._show_grid:
            pen = QPen(QColor(93, 107, 130, 125), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            segments: set[tuple[int, int, int, int]] = set()
            for zone in self._zones:
                left, top = round(zone.left()), round(zone.top())
                right, bottom = round(zone.right()), round(zone.bottom())
                segments.update(
                    {
                        (left, top, right, top),
                        (left, bottom, right, bottom),
                        (left, top, left, bottom),
                        (right, top, right, bottom),
                    }
                )
            for x1, y1, x2, y2 in segments:
                painter.drawLine(x1, y1, x2, y2)


class PreviewPane(QFrame):
    """A fixed A4 preview with a synchronized page selector."""

    def __init__(self, title: str = "Предпросмотр", monochrome: bool = False) -> None:
        super().__init__()
        self.monochrome = monochrome
        self.text_color: QColor | None = None
        self.background_color: QColor | None = None
        self.setObjectName("previewPanel")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 12)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("previewTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setWordWrap(True)
        self.title_label.setFixedHeight(24)
        layout.addWidget(self.title_label)

        self.page = QFrame()
        self.page.setObjectName("a4Page")
        self.page.setFixedSize(500, 707)
        page_layout = QVBoxLayout(self.page)
        page_layout.setContentsMargins(20, 20, 20, 20)
        self.content = QTextEdit()
        self.content.setReadOnly(True)
        self.content.setFrameShape(QFrame.Shape.NoFrame)
        self.content.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.content.setStyleSheet("background: transparent; color: #252a32; font-family: Arial; font-size: 10pt;")
        self.content.document().setDocumentMargin(0)
        self.content.document().setDefaultStyleSheet("p { margin: 0; white-space: pre-wrap; }")
        self.content.setTabStopDistance(32)
        page_layout.addWidget(self.content)
        layout.addWidget(self.page, alignment=Qt.AlignmentFlag.AlignHCenter)

        self._background_pattern_overlay = BackgroundPatternOverlay(self.page)
        self._background_pattern_overlay.setGeometry(self.page.rect())
        self._background_pattern_overlay.lower()
        self.content.raise_()

        self._monochrome_overlay = QLabel(self.page)
        self._monochrome_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._monochrome_overlay.setGeometry(self.page.rect())
        self._monochrome_overlay.hide()

        self.pages: list[str] = []
        self.set_document_paragraphs([])

    def set_document_paragraphs(self, paragraphs: list[str]) -> None:
        """Split formatted paragraphs across pages based on the A4 text area."""
        paragraphs = paragraphs or ["<p>Загрузите документ Word</p>"]
        measure = QTextDocument(self.content)
        measure.setDocumentMargin(0)
        measure.setDefaultFont(self.content.font())
        measure.setDefaultStyleSheet("p { margin: 0; white-space: pre-wrap; }")
        measure.setTextWidth(max(1, self.content.width()))
        max_height = max(1, self.content.height() - 6)

        # A single very long paragraph can itself span multiple preview pages.
        # Split that exceptional case into fitting text blocks so no content is clipped.
        fitting_paragraphs: list[str] = []
        for paragraph in paragraphs:
            measure.setHtml("<html><body>" + paragraph + "</body></html>")
            if measure.size().height() <= max_height:
                fitting_paragraphs.append(paragraph)
                continue
            words = measure.toPlainText().split()
            chunk: list[str] = []
            for word in words:
                candidate = " ".join((*chunk, word))
                measure.setHtml(f"<p>{escape(candidate)}</p>")
                if chunk and measure.size().height() > max_height:
                    fitting_paragraphs.append(f"<p>{escape(' '.join(chunk))}</p>")
                    chunk = [word]
                else:
                    chunk.append(word)
            if chunk:
                fitting_paragraphs.append(f"<p>{escape(' '.join(chunk))}</p>")

        self.pages = []
        current: list[str] = []
        for paragraph in fitting_paragraphs:
            candidate = current + [paragraph]
            measure.setHtml("<html><body>" + "".join(candidate) + "</body></html>")
            if current and measure.size().height() > max_height:
                self.pages.append("<html><body>" + "".join(current) + "</body></html>")
                current = [paragraph]
            else:
                current = candidate
        if current:
            self.pages.append("<html><body>" + "".join(current) + "</body></html>")

        self.show_page(1)

    @property
    def page_count(self) -> int:
        """Return the number of pages currently available in this preview."""
        return len(self.pages)

    def show_page(self, page_number: int) -> None:
        """Display the requested one-based page number."""
        page = self.pages[page_number - 1] if self.pages else "<p></p>"
        self.content.setHtml(page)
        self._apply_text_color()
        self._refresh_monochrome_overlay()

    def set_text_color(self, color: QColor | None) -> None:
        """Override all text colors, or clear the override with ``None``."""
        self.text_color = QColor(color) if color is not None else None
        self._apply_text_color()
        self._refresh_monochrome_overlay()

    def _apply_text_color(self) -> None:
        if self.text_color is None:
            return
        cursor = QTextCursor(self.content.document())
        cursor.select(QTextCursor.SelectionType.Document)
        text_format = QTextCharFormat()
        text_format.setForeground(self.text_color)
        cursor.mergeCharFormat(text_format)

    def set_background_color(self, color: QColor | None) -> None:
        """Set the page background override, or restore the white paper preview."""
        self.background_color = QColor(color) if color is not None else None
        page_color = self.background_color.name() if self.background_color is not None else "#ffffff"
        self.page.setStyleSheet(
            f"QFrame#a4Page {{ background-color: {page_color}; border: 1px solid #c9ced8; }}"
        )
        self._refresh_monochrome_overlay()

    def set_background_pattern(
        self,
        image: QImage | None,
        zones: list[QRectF] | None = None,
        show_grid: bool = False,
    ) -> None:
        """Set the generated pattern shown beneath document text."""
        self._background_pattern_overlay.set_pattern(image, zones, show_grid)
        self._refresh_monochrome_overlay()

    def set_background_grid_visible(self, visible: bool) -> None:
        """Toggle the grid without changing the generated background image."""
        self._background_pattern_overlay.set_pattern(
            self._background_pattern_overlay._image,
            self._background_pattern_overlay._zones,
            visible,
        )
        self._refresh_monochrome_overlay()

    def _refresh_monochrome_overlay(self) -> None:
        """Render a grayscale display overlay without changing document colors."""
        if not self.monochrome:
            self._monochrome_overlay.hide()
            return

        self._monochrome_overlay.hide()
        image = QImage(self.page.size(), QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.white)
        painter = QPainter(image)
        self.page.render(painter, QPoint())
        painter.end()
        grayscale = image.convertToFormat(QImage.Format.Format_Grayscale8)
        display_image = grayscale.convertToFormat(QImage.Format.Format_RGB32)
        self._monochrome_overlay.setGeometry(self.page.rect())
        self._monochrome_overlay.setPixmap(QPixmap.fromImage(display_image))
        self._monochrome_overlay.show()
        self._monochrome_overlay.raise_()

    def set_monochrome(self, enabled: bool) -> None:
        """Switch the preview's monochrome state."""
        self.monochrome = enabled
        self._refresh_monochrome_overlay()
