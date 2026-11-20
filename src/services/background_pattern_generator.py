"""Generate evenly distributed punctuation patterns for A4 pages."""

import math
import random

from PySide6.QtCore import QRectF, QPointF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QImage,
    QPainter,
    QPen,
    QPolygonF,
)


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
        """Render punctuation marks in a regular grid of page zones."""
        return self.generate_background_pattern(
            size,
            zone_count,
            median_text_size_pt,
            minimum_coefficient,
            maximum_coefficient,
            color,
            punctuation=True,
            shapes=False,
            seed=seed,
        )

    def generate_background_pattern(
        self,
        size: tuple[int, int],
        zone_count: int,
        median_text_size_pt: float,
        minimum_coefficient: float,
        maximum_coefficient: float,
        color: QColor | str,
        punctuation: bool,
        shapes: bool,
        seed: int | None = None,
    ) -> tuple[QImage, list[QRectF]]:
        """Render selected fill types with one instance of each per zone."""
        width, height = size
        image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        zones = self.zone_rectangles(size, zone_count)
        generator = random.Random(seed)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        shape_names = ("square", "circle", "triangle")
        shape_zone_indices: set[int] = set()
        if shapes:
            column_count = len({zone.left() for zone in zones})
            shuffled_indices = list(range(len(zones)))
            generator.shuffle(shuffled_indices)
            occupied_cells: list[tuple[int, int]] = []
            for zone_index in shuffled_indices:
                row, column = divmod(zone_index, column_count)
                if any(
                    abs(row - occupied_row) <= 1
                    and abs(column - occupied_column) <= 1
                    for occupied_row, occupied_column in occupied_cells
                ):
                    continue
                shape_zone_indices.add(zone_index)
                occupied_cells.append((row, column))

        for zone_index, zone in enumerate(zones):
            if punctuation:
                coefficient = generator.uniform(minimum_coefficient, maximum_coefficient)
                font_size = max(
                    1,
                    round(median_text_size_pt * coefficient * height / self.A4_HEIGHT_POINTS),
                )
                font = QFont("Arial")
                # Scaling the font uniformly keeps glyph height and stroke
                # thickness tied to the same text-size coefficient.
                font.setPixelSize(font_size)
                painter.setFont(font)
                symbol = generator.choice(self.SYMBOLS)
                bounds = QFontMetricsF(font).boundingRect(symbol)
                point = QPointF(
                    generator.uniform(zone.left(), zone.right()),
                    generator.uniform(zone.top(), zone.bottom()),
                )
                painter.setPen(QColor(color))
                painter.save()
                painter.translate(point)
                painter.rotate(generator.uniform(0.0, 360.0))
                painter.drawText(QPointF(-bounds.center().x(), -bounds.center().y()), symbol)
                painter.restore()

            if zone_index in shape_zone_indices:
                coefficient = generator.uniform(minimum_coefficient, maximum_coefficient)
                size_factor = generator.uniform(1.5, 4.0)
                shape_size = max(
                    1.0,
                    median_text_size_pt
                    * size_factor
                    * coefficient
                    * height
                    / self.A4_HEIGHT_POINTS,
                )
                stroke_width = max(
                    1.0,
                    median_text_size_pt
                    * coefficient
                    * 0.09
                    * height
                    / self.A4_HEIGHT_POINTS,
                )
                point = QPointF(
                    generator.uniform(zone.left(), zone.right()),
                    generator.uniform(zone.top(), zone.bottom()),
                )
                painter.setPen(QPen(QColor(color), stroke_width))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.save()
                painter.translate(point)
                painter.rotate(generator.uniform(0.0, 360.0))
                half_size = shape_size / 2
                shape_name = generator.choice(shape_names)
                if shape_name == "square":
                    painter.drawRect(QRectF(-half_size, -half_size, shape_size, shape_size))
                elif shape_name == "circle":
                    painter.drawEllipse(QRectF(-half_size, -half_size, shape_size, shape_size))
                else:
                    painter.drawPolygon(
                        QPolygonF(
                            [
                                QPointF(0, -half_size),
                                QPointF(half_size, half_size),
                                QPointF(-half_size, half_size),
                            ]
                        )
                    )
                painter.restore()

        painter.end()
        return image, zones
