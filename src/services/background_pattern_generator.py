"""Generate evenly distributed punctuation patterns for A4 pages."""

import math
import random

from PySide6.QtCore import QRectF, QPointF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPainter


class BackgroundPatternGenerator:
    """Create transparent background images with one symbol in each zone."""

    SYMBOLS = ",.!?/"
    A4_HEIGHT_POINTS = 841.89

    def zone_rectangles(self, size: tuple[int, int], zone_count: int) -> list[QRectF]:
        """Divide the page into a regular matrix near the requested zone count."""
        width, height = size
        zone_count = max(1, zone_count)
        aspect_ratio = width / max(1, height)
        column_count = max(1, round(math.sqrt(zone_count * aspect_ratio)))
        row_count = max(1, round(zone_count / column_count))
        cell_width = width / column_count
        cell_height = height / row_count
        return [
            QRectF(column * cell_width, row * cell_height, cell_width, cell_height)
            for row in range(row_count)
            for column in range(column_count)
        ]

    def generate_punctuation_pattern(
        self,
        size: tuple[int, int],
        zone_count: int,
        median_text_size_pt: float,
        minimum_coefficient: float,
        maximum_coefficient: float,
        color: QColor | str,
        seed: int | None = None,
    ) -> tuple[QImage, list[QRectF]]:
        """Render a random punctuation symbol in every equal-area page zone."""
        width, height = size
        image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        zones = self.zone_rectangles(size, zone_count)
        generator = random.Random(seed)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setPen(QColor(color))

        for zone in zones:
            coefficient = generator.uniform(minimum_coefficient, maximum_coefficient)
            font_size = max(
                1,
                round(median_text_size_pt * coefficient * height / self.A4_HEIGHT_POINTS),
            )
            font = QFont("Arial")
            font.setPixelSize(font_size)
            painter.setFont(font)
            metrics = QFontMetricsF(font)
            symbol = generator.choice(self.SYMBOLS)
            bounds = metrics.boundingRect(symbol)
            edge_margin = math.hypot(bounds.width(), bounds.height()) / 2
            left = max(zone.left(), edge_margin)
            right = min(zone.right(), width - edge_margin)
            top = max(zone.top(), edge_margin)
            bottom = min(zone.bottom(), height - edge_margin)
            if left > right:
                left = right = min(width - edge_margin, max(edge_margin, zone.center().x()))
            if top > bottom:
                top = bottom = min(height - edge_margin, max(edge_margin, zone.center().y()))
            point = QPointF(
                generator.uniform(left, right),
                generator.uniform(top, bottom),
            )
            painter.save()
            painter.translate(point)
            painter.rotate(generator.uniform(0.0, 360.0))
            painter.drawText(QPointF(-bounds.center().x(), -bounds.center().y()), symbol)
            painter.restore()

        painter.end()
        return image, zones
