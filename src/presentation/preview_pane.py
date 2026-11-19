"""Text preview widgets."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout


class PreviewPane(QFrame):
    """A placeholder panel for a future document preview."""

    def __init__(self, title: str = "Предпросмотр", monochrome: bool = False) -> None:
        super().__init__()
        self.monochrome = monochrome
        self.setObjectName("previewPanel")
        self.setMinimumSize(220, 230)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("previewTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        self.content_label = QLabel()
        self.content_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content_label.setWordWrap(True)
        self.content_label.setStyleSheet("color: #a1a7b1;")
        layout.addWidget(self.content_label, 1)

    def render_text(self, text: str) -> None:
        """Display preview text when document processing is connected."""
        self.content_label.setText(text)

    def set_monochrome(self, enabled: bool) -> None:
        """Switch the preview's monochrome state."""
        self.monochrome = enabled
