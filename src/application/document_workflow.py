"""Coordinates document loading, transformation and saving."""


class DocumentWorkflow:
    """Application-level workflow for processing a Word document."""

    def load_document(self, file_path: str) -> None:
        """Load a document and prepare its preview data."""
        pass

    def apply_background(self) -> None:
        """Apply the selected background treatment to the document."""
        pass

    def save_document(self, file_path: str) -> None:
        """Save the processed document to the requested path."""
        pass
