"""Desktop application lifecycle."""

import sys

from PySide6.QtWidgets import QApplication

from src.presentation.main_window import MainWindow


class DesktopApp:
    """Owns the desktop application's startup and main window."""

    def __init__(self) -> None:
        self._application = QApplication.instance() or QApplication(sys.argv)
        self._window = MainWindow()

    def run(self) -> None:
        """Start the desktop event loop."""
        self._window.show()
        sys.exit(self._application.exec())
