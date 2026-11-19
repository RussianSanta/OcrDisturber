"""Word page preview widgets."""

from html import escape

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QTextEdit, QVBoxLayout


class PreviewPane(QFrame):
    """A fixed A4 preview with a synchronized page selector."""

    def __init__(self, title: str = "Предпросмотр", monochrome: bool = False) -> None:
        super().__init__()
        self.monochrome = monochrome
        self.setObjectName("previewPanel")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 12)
        layout.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("previewTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setWordWrap(True)
        self.title_label.setFixedHeight(24)
        layout.addWidget(self.title_label)

        self.page = QFrame()
        self.page.setObjectName("a4Page")
        self.page.setFixedSize(438, 620)
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

    def set_monochrome(self, enabled: bool) -> None:
        """Switch the preview's monochrome state."""
        self.monochrome = enabled
