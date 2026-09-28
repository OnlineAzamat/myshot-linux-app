"""Lightshot uslubidagi overlay: muzlatilgan ekran ustida maydonni belgilash.

Har bir monitor uchun alohida to'liq ekranli oyna ochiladi (Wayland'da oynani
ixtiyoriy koordinataga qo'yib bo'lmaydi). Belgilangan maydonni surish va
tutqichlar orqali o'lchamini o'zgartirish mumkin; rasm faqat Saqlash yoki
Nusxalash bosilganda olinadi.
"""
from PyQt6.QtCore import QObject, QPoint, QRect, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import (QColor, QCursor, QGuiApplication, QKeySequence, QPainter,
                         QPainterPath, QPen, QPixmap)
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QToolButton, QWidget

from capture import virtual_geometry

ACCENT = QColor(30, 144, 255)
DIM = QColor(0, 0, 0, 110)
HANDLE_SIZE = 7   # chiziladigan tutqich o'lchami
HANDLE_HIT = 8    # tutqichni ushlash radiusi
MIN_SIZE = 4      # bundan kichik belgilash bekor qilinadi

# Tutqich nomidagi harflar qaysi tomon o'zgarishini bildiradi: l/r/t/b
HANDLE_CURSORS = {
    "lt": Qt.CursorShape.SizeFDiagCursor, "rb": Qt.CursorShape.SizeFDiagCursor,
    "rt": Qt.CursorShape.SizeBDiagCursor, "lb": Qt.CursorShape.SizeBDiagCursor,
    "l": Qt.CursorShape.SizeHorCursor, "r": Qt.CursorShape.SizeHorCursor,
    "t": Qt.CursorShape.SizeVerCursor, "b": Qt.CursorShape.SizeVerCursor,
}


def _rect_from_points(a, b):
    return QRect(QPoint(min(a.x(), b.x()), min(a.y(), b.y())),
                 QPoint(max(a.x(), b.x()), max(a.y(), b.y())))


class ActionBar(QFrame):
    """Belgilangan maydon yonidagi amallar paneli."""
    triggered = pyqtSignal(str)

    BUTTONS = (
        ("save", "💾", "Saqlash (Ctrl+S / Enter)"),
        ("copy", "📋", "Buferga nusxalash (Ctrl+C)"),
        ("cancel", "✕", "Bekor qilish (Esc)"),
    )

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("ActionBar")
        self.setStyleSheet("""
            #ActionBar { background: #2b2b2b; border: 1px solid #555; border-radius: 6px; }
            QToolButton { color: white; background: transparent; border: none;
                          border-radius: 4px; padding: 4px 8px; font-size: 16px; }
            QToolButton:hover { background: #454545; }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        for action, text, tooltip in self.BUTTONS:
            button = QToolButton(self)
            button.setText(text)
            button.setToolTip(tooltip)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _=False, a=action: self.triggered.emit(a))
            layout.addWidget(button)
        self.adjustSize()
        self.hide()


class SelectionOverlay(QWidget):
    activated = pyqtSignal()            # shu monitorda yangi belgilash boshlandi
    action_requested = pyqtSignal(str)  # save / copy / cancel

    def __init__(self, screen, background):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("MyShot")
        self.setScreen(screen)
        self.setGeometry(screen.geometry())
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self._background = background  # jismoniy piksellardagi muzlatilgan rasm
        self._selection = QRect()      # mantiqiy koordinatalarda
        self._drag = None              # (turi, boshlang'ich nuqta, boshlang'ich maydon)

        self._bar = ActionBar(self)
        self._bar.triggered.connect(self.action_requested)

    # --- ommaviy API ----------------------------------------------------

    def has_selection(self):
        return self._selection.isValid()

    def clear_selection(self):
        self._selection = QRect()
        self._drag = None
        self._bar.hide()
        self.update()

    def selected_pixmap(self):
        """Belgilangan maydonni asl (jismoniy) o'lchamda qaytaradi."""
        sx = self._background.width() / self.width()
        sy = self._background.height() / self.height()
        s = self._selection
        source = QRect(round(s.x() * sx), round(s.y() * sy),
                       round(s.width() * sx), round(s.height() * sy))
        return self._background.copy(source)

    # --- yordamchilar ---------------------------------------------------

    def _handles(self):
        s = self._selection
        cx, cy = s.center().x(), s.center().y()
        return {
            "lt": s.topLeft(), "t": QPoint(cx, s.top()), "rt": s.topRight(),
            "r": QPoint(s.right(), cy), "rb": s.bottomRight(), "b": QPoint(cx, s.bottom()),
            "lb": s.bottomLeft(), "l": QPoint(s.left(), cy),
        }

    def _handle_at(self, pos):
        if not self.has_selection():
            return None
        for name, point in self._handles().items():
            if abs(pos.x() - point.x()) <= HANDLE_HIT and abs(pos.y() - point.y()) <= HANDLE_HIT:
                return name
        return None

    def _update_cursor(self, pos):
        handle = self._handle_at(pos)
        if handle:
            self.setCursor(HANDLE_CURSORS[handle])
        elif self._selection.contains(pos):
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        else:
            self.setCursor(Qt.CursorShape.CrossCursor)

    def _clamp(self, pos):
        return QPoint(max(0, min(pos.x(), self.width() - 1)),
                      max(0, min(pos.y(), self.height() - 1)))

    def _place_bar(self):
        bar, s, margin = self._bar, self._selection, 6
        bar.adjustSize()
        x = s.right() - bar.width() + 1
        y = s.bottom() + margin + 1
        if y + bar.height() > self.height():      # pastda joy yo'q – tepaga
            y = s.top() - bar.height() - margin
        if y < 0:                                  # tepada ham yo'q – ichkariga
            y = s.bottom() - bar.height() - margin
        x = max(0, min(x, self.width() - bar.width()))
        bar.move(x, y)
        bar.show()
        bar.raise_()

    # --- sichqoncha -----------------------------------------------------

    def mousePressEvent(self, event):
        pos = self._clamp(event.position().toPoint())
        if event.button() == Qt.MouseButton.RightButton:
            # O'ng tugma: avval belgilashni tozalaydi, ikkinchi marta – chiqish
            if self.has_selection():
                self.clear_selection()
            else:
                self.action_requested.emit("cancel")
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return

        handle = self._handle_at(pos)
        if handle:
            self._drag = (handle, pos, QRect(self._selection))
        elif self._selection.contains(pos):
            self._drag = ("move", pos, QRect(self._selection))
        else:
            self._drag = ("new", pos, None)
            self._selection = QRect(pos, pos)
            self.activated.emit()
        self._bar.hide()
        self.update()

    def mouseMoveEvent(self, event):
        pos = self._clamp(event.position().toPoint())
        if self._drag is None:
            self._update_cursor(pos)
            return

        kind, start, start_rect = self._drag
        if kind == "new":
            self._selection = _rect_from_points(start, pos)
        elif kind == "move":
            rect = start_rect.translated(pos - start)
            rect.moveLeft(max(0, min(rect.left(), self.width() - rect.width())))
            rect.moveTop(max(0, min(rect.top(), self.height() - rect.height())))
            self._selection = rect
        else:
            delta = pos - start
            left, top = start_rect.left(), start_rect.top()
            right, bottom = start_rect.right(), start_rect.bottom()
            if "l" in kind:
                left += delta.x()
            if "r" in kind:
                right += delta.x()
            if "t" in kind:
                top += delta.y()
            if "b" in kind:
                bottom += delta.y()
            self._selection = _rect_from_points(QPoint(left, top), QPoint(right, bottom))
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or self._drag is None:
            return
        self._drag = None
        if self._selection.width() < MIN_SIZE or self._selection.height() < MIN_SIZE:
            self.clear_selection()
        else:
            self._place_bar()
        self._update_cursor(self._clamp(event.position().toPoint()))
        self.update()

    # --- klaviatura -----------------------------------------------------

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.action_requested.emit("cancel")
        elif not self.has_selection():
            super().keyPressEvent(event)
        elif event.matches(QKeySequence.StandardKey.Copy):
            self.action_requested.emit("copy")
        elif (event.matches(QKeySequence.StandardKey.Save)
              or event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)):
            self.action_requested.emit("save")
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        # Oyna tashqaridan yopilsa (masalan Alt+F4) ham sessiya tugashi kerak
        self.action_requested.emit("cancel")
        super().closeEvent(event)

    # --- chizish --------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(QRectF(self.rect()), self._background, QRectF(self._background.rect()))

        dim = QPainterPath()
        dim.addRect(QRectF(self.rect()))
        if self.has_selection():
            dim.addRect(QRectF(self._selection))  # OddEven qoidasi bilan "teshik" hosil bo'ladi
        painter.fillPath(dim, DIM)

        if not self.has_selection():
            return

        painter.setPen(QPen(ACCENT, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(self._selection).adjusted(0.5, 0.5, -0.5, -0.5))

        painter.setBrush(Qt.GlobalColor.white)
        half = HANDLE_SIZE // 2
        for point in self._handles().values():
            painter.drawRect(point.x() - half, point.y() - half, HANDLE_SIZE, HANDLE_SIZE)

        self._paint_size_label(painter)

    def _paint_size_label(self, painter):
        # Haqiqiy (jismoniy) piksellardagi o'lcham
        sx = self._background.width() / self.width()
        sy = self._background.height() / self.height()
        text = f"{round(self._selection.width() * sx)} × {round(self._selection.height() * sy)}"
        metrics = painter.fontMetrics()
        box = QRect(0, 0, metrics.horizontalAdvance(text) + 12, metrics.height() + 6)
        box.moveBottomLeft(self._selection.topLeft() - QPoint(0, 5))
        if box.top() < 0:
            box.moveTopLeft(self._selection.topLeft() + QPoint(5, 5))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 170))
        painter.drawRoundedRect(QRectF(box), 4, 4)
        painter.setPen(Qt.GlobalColor.white)
        painter.drawText(box, Qt.AlignmentFlag.AlignCenter, text)


class CaptureSession(QObject):
    """Bitta rasmga olish jarayoni: barcha monitorlardagi overlay'larni boshqaradi."""
    finished = pyqtSignal(str, str)  # (amal: save/copy/cancel/error, fayl yo'li)

    def __init__(self, image, save_path_factory, parent=None):
        super().__init__(parent)
        self._save_path_factory = save_path_factory
        self._done = False
        self._overlays = []

        screens = QGuiApplication.screens()
        virtual = virtual_geometry(screens)
        sx = image.width() / virtual.width()
        sy = image.height() / virtual.height()
        for screen in screens:
            g = screen.geometry().translated(-virtual.topLeft())
            source = QRect(round(g.x() * sx), round(g.y() * sy),
                           round(g.width() * sx), round(g.height() * sy))
            overlay = SelectionOverlay(screen, QPixmap.fromImage(image.copy(source)))
            overlay.activated.connect(lambda o=overlay: self._on_activated(o))
            overlay.action_requested.connect(lambda action, o=overlay: self._on_action(o, action))
            self._overlays.append(overlay)

    def start(self):
        for overlay in self._overlays:
            overlay.showFullScreen()
        target = self._overlay_under_cursor()
        target.raise_()
        target.activateWindow()

    def _overlay_under_cursor(self):
        screen = QGuiApplication.screenAt(QCursor.pos())
        for overlay in self._overlays:
            if overlay.screen() is screen:
                return overlay
        return self._overlays[0]

    def _on_activated(self, source):
        for overlay in self._overlays:
            if overlay is not source:
                overlay.clear_selection()

    def _on_action(self, overlay, action):
        if self._done:
            return
        path = ""
        if action == "save" and overlay.has_selection():
            path = self._save_path_factory()
            if not overlay.selected_pixmap().save(path, "PNG"):
                action = "error"
        elif action == "copy" and overlay.has_selection():
            # Wayland'da buferga yozish oyna fokusda turganda bajarilishi kerak
            QGuiApplication.clipboard().setPixmap(overlay.selected_pixmap())
        else:
            action = "cancel"

        self._done = True
        for o in self._overlays:
            o.close()
        self._overlays.clear()
        self.finished.emit(action, path)
