"""Generation and validation of colors with matching OCR grayscale values."""

from PySide6.QtGui import QColor


class EqualLuminanceColorGenerator:
    """Find colors that collapse to the same Rec. 601 grayscale value.

    This matches the common grayscale conversion used by OCR preprocessing,
    including OpenCV's BGR-to-gray conversion (up to its integer rounding).
    """

    @staticmethod
    def grayscale_value(color: QColor | str) -> int:
        """Return the rounded Rec. 601 grayscale intensity in [0, 255]."""
        color = QColor(color) if isinstance(color, str) else color
        return round(0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue())

    def find_equal_luminance_color(self, color: QColor | str) -> QColor:
        """Return the most RGB-distant color with the same grayscale value."""
        source = QColor(color) if isinstance(color, str) else QColor(color)
        if not source.isValid():
            raise ValueError("color must be a valid QColor or color string")

        target = self.grayscale_value(source)
        source_channels = (source.red(), source.green(), source.blue())
        best = source_channels
        best_distance = -1

        # For every red/green pair, solve the grayscale equation for blue.
        # Testing the rounded value and its neighbors finds every blue channel
        # that maps to the target intensity, without searching 16 million RGBs.
        for red in range(256):
            for green in range(256):
                blue_exact = (target - 0.299 * red - 0.587 * green) / 0.114
                base = round(blue_exact)
                for blue in (base - 1, base, base + 1):
                    if not 0 <= blue <= 255:
                        continue
                    candidate = (red, green, blue)
                    if self.grayscale_value(QColor(*candidate)) != target:
                        continue
                    distance = sum((a - b) ** 2 for a, b in zip(candidate, source_channels))
                    if distance > best_distance:
                        best, best_distance = candidate, distance

        return QColor(*best)

    def generate(self, count: int, brightness: float) -> list[str]:
        """Generate maximally separated colors near a grayscale brightness.

        ``brightness`` is an 8-bit grayscale intensity (0..255). Each result
        uses the same grayscale value; colors are deterministic variants.
        """
        if count < 0:
            raise ValueError("count must be non-negative")
        if not 0 <= brightness <= 255:
            raise ValueError("brightness must be in [0, 255]")
        if count == 0:
            return []
        seed = QColor(int(brightness), int(brightness), int(brightness))
        first = self.find_equal_luminance_color(seed)
        colors = [seed.name(), first.name()]
        while len(colors) < count:
            prior = QColor(colors[-1])
            colors.append(self.find_equal_luminance_color(prior).name())
        return colors[:count]

    def are_equally_bright(self, colors: list[str]) -> bool:
        """Return whether all colors map to the same grayscale intensity."""
        if not colors:
            return True
        try:
            values = {self.grayscale_value(color) for color in colors}
        except (TypeError, ValueError):
            return False
        return len(values) == 1
