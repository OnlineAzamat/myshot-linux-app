"""Lightshot uslubidagi overlay: muzlatilgan ekran ustida maydonni belgilash va chizish.

Har bir monitor uchun alohida to'liq ekranli oyna ochiladi (Wayland'da oynani
ixtiyoriy koordinataga qo'yib bo'lmaydi). Belgilangan maydonni surish va
tutqichlar orqali o'lchamini o'zgartirish, uning ustida chizish mumkin; rasm
faqat Saqlash yoki Nusxalash bosilganda olinadi.
"""
from PyQt6.QtCore import QObject, QPoint, QPointF, QRect, QRectF, QSettings, Qt, pyqtSignal
from PyQt6.QtGui import (QColor, QCursor, QGuiApplication, QKeySequence, QPainter,
                         QPainterPath, QPen, QPixmap)
from PyQt6.QtWidgets import QLineEdit, QWidget

from annotations import SHAPES, Text, paint_all, text_font
from capture import virtual_geometry
from toolbar import MAX_WIDTH, MIN_WIDTH, ActionBar, ToolBar

ACCENT = QColor(30, 144, 255)
DIM = QColor(0, 0, 0, 110)
HANDLE_SIZE = 7   # chiziladigan tutqich o'lchami
HANDLE_HIT = 8    # tutqichni ushlash radiusi
MIN_SIZE = 4      # bundan kichik belgilash bekor qilinadi
BAR_MARGIN = 6

DEFAULT_COLOR = "#ff3b30"
DEFAULT_WIDTH = 3

# Tutqich nomidagi harflar qaysi tomon o'zgarishini bildiradi: l/r/t/b
HANDLE_CURSORS = {
    "lt": Qt.CursorShape.SizeFDiagCursor, "rb": Qt.CursorShape.SizeFDiagCursor,
    "rt": Qt.CursorShape.SizeBDiagCursor, "lb": Qt.CursorShape.SizeBDiagCursor,
    "l": Qt.CursorShape.SizeHorCursor, "r": Qt.CursorShape.SizeHorCursor,
    "t": Qt.CursorShape.SizeVerCursor, "b": Qt.CursorShape.SizeVerCursor,
}

# Asboblarni klaviaturadan tanlash
TOOL_KEYS = {
    Qt.Key.Key_P: "pen", Qt.Key.Key_L: "line", Qt.Key.Key_A: "arrow", Qt.Key.Key_R: "rect",
    Qt.Key.Key_E: "ellipse", Qt.Key.Key_M: "marker", Qt.Key.Key_T: "text",
}


def _rect_from_points(a, b):
    return QRect(QPoint(min(a.x(), b.x()), min(a.y(), b.y())),
                 QPoint(max(a.x(), b.x()), max(a.y(), b.y())))


def _settings():
    return QSettings("MyShot", "MyShot")


class TextInput(QLineEdit):
    """Matn asbobi uchun joyida tahrirlash maydoni."""
    committed = pyqtSignal(str)

    def __init__(self, parent, pos, color, width):
        super().__init__(parent)
        self._done = False
        self.setFont(text_font(width))
        self.setFrame(False)
        self.setTextMargins(0, 0, 0, 0)
        self.setStyleSheet(f"QLineEdit {{ background: transparent; color: {color.name()};"
                           f" border: 1px dashed {color.name()}; padding: 0; }}")
        # QLineEdit matnni ichki chegaradan biroz surib chizadi – shuni hisobga olamiz
        self.move(pos - QPoint(3, 3))
        self.textChanged.connect(self._fit)
        self._fit()
        self.show()
        self.setFocus()

    def _fit(self):
        metrics = self.fontMetrics()
        self.resize(max(40, metrics.horizontalAdvance(self.text() + "  ")), metrics.height() + 6)

    def finish(self, commit=True):
        if self._done:
            return
        self._done = True
        self.committed.emit(self.text() if commit else "")
        self.deleteLater()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.finish(commit=False)
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.finish()
        else:
            super().keyPressEvent(event)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.finish()


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

        settings = _settings()
        self._tool = ""
        self._color = QColor(settings.value("color", DEFAULT_COLOR))
        self._width = max(MIN_WIDTH, min(MAX_WIDTH, int(settings.value("width", DEFAULT_WIDTH))))
        self._annotations = []
        self._redo = []
        self._current = None           # hozir chizilayotgan shakl
        self._text_input = None

        self._actions = ActionBar(self)
        self._actions.triggered.connect(self._request_action)
        self._tools = ToolBar(self, self._color, self._width)
        self._tools.tool_changed.connect(self._set_tool)
        self._tools.color_changed.connect(self._set_color)
        self._tools.width_changed.connect(self._set_width)
        self._tools.undo_requested.connect(self.undo)
        self._tools.redo_requested.connect(self.redo)

    # --- ommaviy API ----------------------------------------------------

    def has_selection(self):
        return self._selection.isValid()

    def clear_selection(self):
        self._finish_text(commit=False)
        self._selection = QRect()
        self._drag = None
        self._annotations.clear()
        self._redo.clear()
        self._hide_bars()
        self.update()

    def selected_pixmap(self):
        """Belgilangan maydonni chizilganlar bilan birga asl (jismoniy) o'lchamda qaytaradi."""
        self._finish_text()
        sx = self._background.width() / self.width()
        sy = self._background.height() / self.height()
        s = self._selection
        source = QRect(round(s.x() * sx), round(s.y() * sy),
                       round(s.width() * sx), round(s.height() * sy))
        pixmap = self._background.copy(source)
        if self._annotations:
            painter = QPainter(pixmap)
            painter.scale(sx, sy)
            painter.translate(-QPointF(s.topLeft()))
            paint_all(painter, self._annotations)
            painter.end()
        return pixmap

    def undo(self):
        self._finish_text()
        if self._annotations:
            self._redo.append(self._annotations.pop())
            self.update()

    def redo(self):
        if self._redo:
            self._annotations.append(self._redo.pop())
            self.update()

    # --- asbob sozlamalari ----------------------------------------------

    def _set_tool(self, tool):
        self._finish_text()
        self._tool = tool
        self._tools.set_tool(tool)
        self._update_cursor(self.mapFromGlobal(QCursor.pos()))

    def _set_color(self, color):
        self._color = QColor(color)
        _settings().setValue("color", self._color.name())

    def _set_width(self, width):
        self._width = width
        self._tools.set_width(width)
        _settings().setValue("width", width)

    def _request_action(self, action):
        self._finish_text()
        self.action_requested.emit(action)

    # --- matn -----------------------------------------------------------

    def _start_text(self, pos):
        self._finish_text()
        self._text_input = TextInput(self, pos, self._color, self._width)
        color, width = QColor(self._color), self._width
        self._text_input.committed.connect(lambda text: self._add_text(pos, color, width, text))

    def _add_text(self, pos, color, width, text):
        self._text_input = None
        annotation = Text(color, width, QPointF(pos), text)
        if not annotation.is_empty():
            self._annotations.append(annotation)
            self._redo.clear()
        self.setFocus()
        self.update()

    def _finish_text(self, commit=True):
        if self._text_input is not None:
            self._text_input.finish(commit)

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
            if self._tool == "text":
                self.setCursor(Qt.CursorShape.IBeamCursor)
            elif self._tool:
                self.setCursor(Qt.CursorShape.CrossCursor)
            else:
                self.setCursor(Qt.CursorShape.SizeAllCursor)
        else:
            self.setCursor(Qt.CursorShape.CrossCursor)

    def _clamp(self, pos):
        return QPoint(max(0, min(pos.x(), self.width() - 1)),
                      max(0, min(pos.y(), self.height() - 1)))

    def _hide_bars(self):
        self._actions.hide()
        self._tools.hide()

    def _place_bars(self):
        s = self._selection
        actions, tools = self._actions, self._tools
        actions.adjustSize()
        tools.adjustSize()

        # Amallar paneli – maydon ostida, o'ng tomonga tekislangan
        x = s.right() - actions.width() + 1
        y = s.bottom() + BAR_MARGIN + 1
        if y + actions.height() > self.height():      # pastda joy yo'q – tepaga
            y = s.top() - actions.height() - BAR_MARGIN
        if y < 0:                                      # tepada ham yo'q – ichkariga
            y = s.bottom() - actions.height() - BAR_MARGIN
        actions.move(max(0, min(x, self.width() - actions.width())), y)

        # Asboblar paneli – maydonning o'ng tomonida, yuqoriga tekislangan
        x = s.right() + BAR_MARGIN + 1
        if x + tools.width() > self.width():           # o'ngda joy yo'q – chapga
            x = s.left() - tools.width() - BAR_MARGIN
        if x < 0:                                      # chapda ham yo'q – ichkariga
            x = s.right() - tools.width() - BAR_MARGIN
        y = max(0, min(s.top(), self.height() - tools.height()))
        tools.move(max(0, x), y)

        for bar in (actions, tools):
            bar.show()
            bar.raise_()

    # --- sichqoncha -----------------------------------------------------

    def mousePressEvent(self, event):
        pos = self._clamp(event.position().toPoint())
        self._finish_text()
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
        inside = self._selection.contains(pos)
        if handle:
            self._drag = (handle, pos, QRect(self._selection))
        elif inside and self._tool == "text":
            self._start_text(pos)
            return
        elif inside and self._tool:
            self._current = SHAPES[self._tool](self._color, self._width, QPointF(pos))
            self._drag = ("draw", pos, None)
            return
        elif inside:
            self._drag = ("move", pos, QRect(self._selection))
        elif self._annotations:
            # Chizilganlarni tasodifan yo'qotib qo'ymaslik uchun yangi maydon boshlanmaydi
            return
        else:
            self._drag = ("new", pos, None)
            self._selection = QRect(pos, pos)
            self.activated.emit()
        self._hide_bars()
        self.update()

    def mouseMoveEvent(self, event):
        if self._drag is None:
            self._update_cursor(self._clamp(event.position().toPoint()))
            return

        kind, start, start_rect = self._drag
        if kind == "draw":
            shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            self._current.update(event.position(), shift)
            self.update()
            return

        pos = self._clamp(event.position().toPoint())
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
        kind = self._drag[0]
        self._drag = None

        if kind == "draw":
            if not self._current.is_empty():
                self._annotations.append(self._current)
                self._redo.clear()
            self._current = None
        elif self._selection.width() < MIN_SIZE or self._selection.height() < MIN_SIZE:
            self.clear_selection()
        else:
            self._place_bars()
        self._update_cursor(self._clamp(event.position().toPoint()))
        self.update()

    def wheelEvent(self, event):
        # Lightshot'dagidek: g'ildirak chiziq qalinligini o'zgartiradi
        if not self.has_selection():
            return
        step = 1 if event.angleDelta().y() > 0 else -1 if event.angleDelta().y() < 0 else 0
        width = max(MIN_WIDTH, min(MAX_WIDTH, self._width + step))
        if width != self._width:
            self._set_width(width)

    # --- klaviatura -----------------------------------------------------

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.action_requested.emit("cancel")
        elif not self.has_selection():
            super().keyPressEvent(event)
        elif event.matches(QKeySequence.StandardKey.Undo):
            self.undo()
        elif (event.matches(QKeySequence.StandardKey.Redo)
              or (key == Qt.Key.Key_Z and event.modifiers() == (Qt.KeyboardModifier.ControlModifier
                                                                | Qt.KeyboardModifier.ShiftModifier))):
            self.redo()
        elif event.matches(QKeySequence.StandardKey.Copy):
            self._request_action("copy")
        elif event.matches(QKeySequence.StandardKey.Save) or key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._request_action("save")
        elif key in TOOL_KEYS and event.modifiers() == Qt.KeyboardModifier.NoModifier:
            tool = TOOL_KEYS[key]
            self._set_tool("" if self._tool == tool else tool)
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

        painter.save()
        painter.setClipRect(self._selection)
        paint_all(painter, self._annotations + ([self._current] if self._current else []))
        painter.restore()

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
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
