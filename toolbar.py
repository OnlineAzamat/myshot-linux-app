"""Overlay panellari: chizish asboblari (vertikal) va amallar (gorizontal)."""
from PyQt6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PyQt6.QtWidgets import (QColorDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
                             QMenu, QSlider, QToolButton, QVBoxLayout, QWidget, QWidgetAction)

MIN_WIDTH, MAX_WIDTH = 1, 30

TOOLS = (
    ("pen", "Pen (P)"),
    ("line", "Line (L)"),
    ("arrow", "Arrow (A)"),
    ("rect", "Rectangle (R)"),
    ("ellipse", "Ellipse (E)"),
    ("marker", "Marker (M)"),
    ("text", "Text (T)"),
)

PALETTE = ("#ff3b30", "#ff9500", "#ffcc00", "#34c759",
           "#007aff", "#af52de", "#000000", "#ffffff")

BAR_STYLE = """
    #Bar { background: #2b2b2b; border: 1px solid #555; border-radius: 6px; }
    QToolButton { color: white; background: transparent; border: none; border-radius: 4px;
                  padding: 3px; font-size: 16px; min-width: 26px; min-height: 26px; }
    QToolButton:hover { background: #454545; }
    QToolButton:checked { background: #1e90ff; }
    QToolButton::menu-indicator { image: none; width: 0; }
"""

MENU_STYLE = """
    QMenu { background: #2b2b2b; border: 1px solid #555; border-radius: 6px; padding: 6px; }
    QLabel { color: white; }
    QToolButton { border: 1px solid #555; border-radius: 4px; }
    QToolButton:hover { border-color: white; }
    QPushButton, #Custom { color: white; background: #3a3a3a; border-radius: 4px; padding: 4px 8px; }
"""

ICON_SIZE = 24


# --- ikonkalar ----------------------------------------------------------

def _icon(draw):
    pixmap = QPixmap(ICON_SIZE * 2, ICON_SIZE * 2)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("white"), 2, Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    draw(painter)
    painter.end()
    return QIcon(pixmap)


def _draw_pen(p):
    path = QPainterPath(QPointF(5, 18))
    path.cubicTo(QPointF(9, 6), QPointF(13, 22), QPointF(19, 6))
    p.drawPath(path)


def _draw_line(p):
    p.drawLine(QPointF(5, 19), QPointF(19, 5))


def _draw_arrow(p):
    p.drawLine(QPointF(5, 19), QPointF(16, 8))
    p.setBrush(QColor("white"))
    p.drawPolygon(QPolygonF([QPointF(19, 5), QPointF(11.5, 7), QPointF(17, 12.5)]))


def _draw_rect(p):
    p.drawRect(QRectF(5, 7, 14, 10))


def _draw_ellipse(p):
    p.drawEllipse(QRectF(4, 7, 16, 10))


def _draw_marker(p):
    p.setPen(QPen(QColor(255, 204, 0, 190), 7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
    p.drawLine(QPointF(4, 12), QPointF(20, 12))


def _draw_text(p):
    font = QFont()
    font.setPixelSize(18)
    font.setBold(True)
    p.setFont(font)
    p.drawText(QRectF(0, 0, ICON_SIZE, ICON_SIZE), Qt.AlignmentFlag.AlignCenter, "T")


TOOL_ICONS = {
    "pen": _draw_pen, "line": _draw_line, "arrow": _draw_arrow, "rect": _draw_rect,
    "ellipse": _draw_ellipse, "marker": _draw_marker, "text": _draw_text,
}


def color_icon(color):
    def draw(p):
        p.setPen(QPen(QColor("white"), 1.5))
        p.setBrush(color)
        p.drawRoundedRect(QRectF(4, 4, 16, 16), 4, 4)
    return _icon(draw)


# --- tugmalar -----------------------------------------------------------

def _button(parent, tooltip, text=None, icon=None, checkable=False):
    button = QToolButton(parent)
    button.setToolTip(tooltip)
    button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setCheckable(checkable)
    if icon is not None:
        button.setIcon(icon)
        button.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
    if text is not None:
        button.setText(text)
    return button


def _separator(parent, vertical):
    line = QFrame(parent)
    line.setFrameShape(QFrame.Shape.HLine if vertical else QFrame.Shape.VLine)
    line.setStyleSheet("color: #555;")
    return line


class _Bar(QFrame):
    def __init__(self, parent, vertical):
        super().__init__(parent)
        self.setObjectName("Bar")
        self.setStyleSheet(BAR_STYLE)
        self._vertical = vertical
        layout = QVBoxLayout(self) if vertical else QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        self.hide()

    def add(self, widget):
        self.layout().addWidget(widget)
        return widget

    def add_separator(self):
        self.layout().addWidget(_separator(self, self._vertical))


class ActionBar(_Bar):
    """Belgilangan maydon ostidagi amallar paneli."""
    triggered = pyqtSignal(str)

    BUTTONS = (
        ("save", "💾", "Save (Ctrl+S / Enter)"),
        ("copy", "📋", "Copy to clipboard (Ctrl+C)"),
        ("cancel", "✕", "Close (Esc)"),
    )

    def __init__(self, parent):
        super().__init__(parent, vertical=False)
        for action, text, tooltip in self.BUTTONS:
            button = self.add(_button(self, tooltip, text=text))
            button.clicked.connect(lambda _=False, a=action: self.triggered.emit(a))
        self.adjustSize()


class ToolBar(_Bar):
    """Chizish asboblari, rang, qalinlik va Undo/Redo."""
    tool_changed = pyqtSignal(str)       # "" – asbob tanlanmagan (maydonni surish rejimi)
    color_changed = pyqtSignal(QColor)
    width_changed = pyqtSignal(int)
    undo_requested = pyqtSignal()
    redo_requested = pyqtSignal()

    def __init__(self, parent, color, width):
        super().__init__(parent, vertical=True)
        self._tool_buttons = {}
        for name, tooltip in TOOLS:
            button = self.add(_button(self, tooltip, icon=_icon(TOOL_ICONS[name]), checkable=True))
            button.clicked.connect(lambda checked, n=name: self._on_tool_clicked(n, checked))
            self._tool_buttons[name] = button

        self.add_separator()
        self._color_button = self.add(_button(self, "Color"))
        self._color_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._color_button.setMenu(self._build_color_menu())

        self._width_button = self.add(_button(self, "Line width (mouse wheel)"))
        self._width_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._width_button.setMenu(self._build_width_menu())
        self._width_button.setStyleSheet("font-size: 12px; font-weight: bold;")

        self.add_separator()
        undo = self.add(_button(self, "Undo (Ctrl+Z)", text="↶"))
        undo.clicked.connect(self.undo_requested)
        redo = self.add(_button(self, "Redo (Ctrl+Shift+Z)", text="↷"))
        redo.clicked.connect(self.redo_requested)

        self.set_color(color)
        self.set_width(width)
        self.adjustSize()

    # --- holat ----------------------------------------------------------

    def set_tool(self, tool):
        for name, button in self._tool_buttons.items():
            button.setChecked(name == tool)

    def set_color(self, color):
        self._color = QColor(color)
        self._color_button.setIcon(color_icon(self._color))

    def set_width(self, width):
        self._width_button.setText(str(width))
        if self._width_slider.value() != width:
            self._width_slider.setValue(width)

    def _on_tool_clicked(self, name, checked):
        # Tanlangan asbobni yana bosish uni o'chiradi
        tool = name if checked else ""
        self.set_tool(tool)
        self.tool_changed.emit(tool)

    # --- rang menyusi ---------------------------------------------------

    def _build_color_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(MENU_STYLE)
        panel = QWidget(menu)
        grid = QGridLayout(panel)
        grid.setContentsMargins(2, 2, 2, 2)
        grid.setSpacing(4)
        for index, value in enumerate(PALETTE):
            swatch = QToolButton(panel)
            swatch.setFixedSize(26, 26)
            swatch.setCursor(Qt.CursorShape.PointingHandCursor)
            swatch.setStyleSheet(f"background: {value};")
            swatch.clicked.connect(lambda _=False, c=value: self._pick_color(menu, QColor(c)))
            grid.addWidget(swatch, index // 4, index % 4)
        custom = QToolButton(panel)
        custom.setObjectName("Custom")
        custom.setText("Custom…")
        custom.setCursor(Qt.CursorShape.PointingHandCursor)
        custom.clicked.connect(lambda: self._pick_custom_color(menu))
        grid.addWidget(custom, 2, 0, 1, 4)
        action = QWidgetAction(menu)
        action.setDefaultWidget(panel)
        menu.addAction(action)
        return menu

    def _pick_color(self, menu, color):
        menu.close()
        self.set_color(color)
        self.color_changed.emit(color)

    def _pick_custom_color(self, menu):
        menu.close()

        def ask():
            color = QColorDialog.getColor(self._color, self.window(), "Choose color",
                                          QColorDialog.ColorDialogOption.DontUseNativeDialog)
            if color.isValid():
                self.set_color(color)
                self.color_changed.emit(color)

        # Menyu to'liq yopilgandan keyin dialogni ochamiz
        QTimer.singleShot(0, ask)

    # --- qalinlik menyusi -----------------------------------------------

    def _build_width_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(MENU_STYLE)
        panel = QWidget(menu)
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(6, 2, 6, 2)
        label = QLabel("Width", panel)
        self._width_slider = QSlider(Qt.Orientation.Horizontal, panel)
        self._width_slider.setRange(MIN_WIDTH, MAX_WIDTH)
        self._width_slider.setFixedWidth(160)
        value = QLabel(panel)
        value.setMinimumWidth(24)
        self._width_slider.valueChanged.connect(lambda v: value.setText(str(v)))
        self._width_slider.valueChanged.connect(self._on_slider)
        layout.addWidget(label)
        layout.addWidget(self._width_slider)
        layout.addWidget(value)
        action = QWidgetAction(menu)
        action.setDefaultWidget(panel)
        menu.addAction(action)
        return menu

    def _on_slider(self, width):
        self._width_button.setText(str(width))
        self.width_changed.emit(width)
