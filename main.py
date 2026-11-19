"""Application entry point."""

from src.presentation.desktop_app import DesktopApp


def main() -> None:
    """Create and run the desktop application."""
    app = DesktopApp()
    app.run()


if __name__ == "__main__":
    main()
