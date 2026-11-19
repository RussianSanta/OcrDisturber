"""Generation and validation of equally bright colors."""


class EqualLuminanceColorGenerator:
    """Creates colors with a shared perceived brightness target."""

    def generate(self, count: int, brightness: float) -> list[str]:
        """Generate a set of colors with the requested brightness."""
        pass

    def are_equally_bright(self, colors: list[str]) -> bool:
        """Check whether colors have approximately equal brightness."""
        pass
