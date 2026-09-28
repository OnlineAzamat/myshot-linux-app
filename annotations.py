"""Belgilangan maydon ustiga chiziladigan shakllar (annotatsiyalar).

Har bir shakl overlay'ning mantiqiy koordinatalarida saqlanadi. Saqlashda
ular kesib olingan rasm ustiga masshtab bilan qayta chiziladi.
"""
import math

from PyQt6.QtCore import QLineF, QPointF, QRectF, QSizeF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF

MARKER_ALPHA = 110
ARROW_ANGLE = math.radians(28)


def text_pixel_size(width):
    """Matn o'lchami chiziq qalinligiga bog'liq: bitta slayder ikkalasini boshqaradi."""
    return 10 + width * 2


def text_font(width):
    font = QFont()
    font.setPixelSize(text_pixel_size(width))
    font.setBold(True)
    return font


def _pen(color, width):
    return QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)


def _snap_angle(start, end):
    """Chiziqni eng yaqin 45° yo'nalishga tekislaydi (Shift)."""
    line = QLineF(start, end)
    angle = round(line.angle() / 45) * 45
    line.setAngle(angle)
    return line.p2()


def _snap_square(start, end):
    """To'rtburchakni kvadratga (ellipsni doiraga) aylantiradi (Shift)."""
    dx, dy = end.x() - start.x(), end.y() - start.y()
    side = max(abs(dx), abs(dy))
    return QPointF(start.x() + math.copysign(side, dx), start.y() + math.copysign(side, dy))


class Annotation:
    def __init__(self, color, width, start):
        self.color = QColor(color)
        self.width = width
        self.start = QPointF(start)
        self.end = QPointF(start)

    def update(self, pos, shift=False):
        self.end = QPointF(pos)

    def is_empty(self):
        return QLineF(self.start, self.end).length() < 2

    def paint(self, painter):
        raise NotImplementedError


class Stroke(Annotation):
    """Qalam: erkin chiziq."""

    def __init__(self, color, width, start):
        super().__init__(color, width, start)
        self.points = [QPointF(start)]

    def update(self, pos, shift=False):
        if QLineF(self.points[-1], QPointF(pos)).length() >= 1:
            self.points.append(QPointF(pos))

    def is_empty(self):
        return False  # bitta bosish ham nuqta qo'yadi

    def _path(self):
        path = QPainterPath(self.points[0])
        if len(self.points) == 1:
            path.lineTo(self.points[0] + QPointF(0.01, 0))
        for point in self.points[1:]:
            path.lineTo(point)
        return path

    def paint(self, painter):
        painter.setPen(_pen(self.color, self.width))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self._path())


class Marker(Stroke):
    """Yarim shaffof keng qalam (matnni ajratib ko'rsatish uchun)."""

    def paint(self, painter):
        color = QColor(self.color)
        color.setAlpha(MARKER_ALPHA)
        painter.setPen(_pen(color, max(8, self.width * 4)))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self._path())


class Line(Annotation):
    def update(self, pos, shift=False):
        self.end = _snap_angle(self.start, QPointF(pos)) if shift else QPointF(pos)

    def paint(self, painter):
        painter.setPen(_pen(self.color, self.width))
        painter.drawLine(self.start, self.end)


class Arrow(Line):
    def paint(self, painter):
        line = QLineF(self.start, self.end)
        length = line.length()
        if length < 1:
            return
        head = min(max(16, self.width * 4.5), length)
        angle = math.atan2(self.end.y() - self.start.y(), self.end.x() - self.start.x())

        def back(offset_angle):
            return QPointF(self.end.x() - head * math.cos(angle + offset_angle),
                           self.end.y() - head * math.sin(angle + offset_angle))

        # Qalin chiziq uchi strelka boshidan chiqib turmasligi uchun uni biroz qisqartiramiz
        shaft_end = line.pointAt(max(0.0, 1 - head * 0.8 / length))
        painter.setPen(_pen(self.color, self.width))
        painter.drawLine(self.start, shaft_end)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.color)
        painter.drawPolygon(QPolygonF([self.end, back(ARROW_ANGLE), back(-ARROW_ANGLE)]))


class Rectangle(Annotation):
    def update(self, pos, shift=False):
        self.end = _snap_square(self.start, QPointF(pos)) if shift else QPointF(pos)

    def is_empty(self):
        return abs(self.end.x() - self.start.x()) < 2 or abs(self.end.y() - self.start.y()) < 2

    def rect(self):
        return QRectF(self.start, self.end).normalized()

    def paint(self, painter):
        painter.setPen(QPen(self.color, self.width, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.SquareCap, Qt.PenJoinStyle.MiterJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self.rect())


class Ellipse(Rectangle):
    def paint(self, painter):
        painter.setPen(_pen(self.color, self.width))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(self.rect())


class Text(Annotation):
    def __init__(self, color, width, start, text):
        super().__init__(color, width, start)
        self.text = text

    def is_empty(self):
        return not self.text.strip()

    def paint(self, painter):
        painter.setPen(self.color)
        painter.setFont(text_font(self.width))
        flags = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextDontClip
        painter.drawText(QRectF(self.start, QSizeF(1, 1)), flags, self.text)


# Sichqoncha bilan chiziladigan asboblar (matn alohida – u klaviaturadan kiritiladi)
SHAPES = {
    "pen": Stroke,
    "line": Line,
    "arrow": Arrow,
    "rect": Rectangle,
    "ellipse": Ellipse,
    "marker": Marker,
}


def paint_all(painter, annotations):
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    for annotation in annotations:
        painter.save()
        annotation.paint(painter)
        painter.restore()
