import os
import signal
import sys
from datetime import datetime

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtNetwork import QLocalServer
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from capture import ScreenCapturer
from hotkeys import AREA_BINDING, HotkeyError, install_area_shortcut
from ipc import ACK, SOCKET_PATH
from overlay import CaptureSession
from version import __version__

# Tray menyusi yopilib, ekrandan yo'qolishiga vaqt beramiz
MENU_CLOSE_DELAY_MS = 250


def get_save_path():
    # Fayl nomini va yo'lini generatsiya qilish
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    save_dir = os.path.expanduser("~/Pictures/Screenshots")
    os.makedirs(save_dir, exist_ok=True)
    return os.path.join(save_dir, f"shot_{timestamp}.png")


class CommandServer(QObject):
    """`myshot.py --area` kabi buyruqlarni ishlab turgan nusxaga yetkazadi."""
    command_received = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._server = QLocalServer(self)
        QLocalServer.removeServer(SOCKET_PATH)  # oldingi ishga tushirishdan qolgan socket
        if not self._server.listen(SOCKET_PATH):
            print(f"Warning: could not open command socket: {self._server.errorString()}",
                  file=sys.stderr)
        self._server.newConnection.connect(self._accept)

    def _accept(self):
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            socket.readyRead.connect(lambda s=socket: self._read(s))
            socket.disconnected.connect(socket.deleteLater)
            self._read(socket)

    def _read(self, socket):
        while socket.canReadLine():
            command = bytes(socket.readLine()).decode(errors="ignore").strip()
            if command:
                socket.write(ACK)
                socket.flush()
                self.command_received.emit(command)


class ScreenshotTrayApp(QObject):
    def __init__(self, show_welcome=True):
        super().__init__()
        self._pending = None   # "area" yoki "full"
        self._session = None

        self.capturer = ScreenCapturer(self)
        self.capturer.captured.connect(self._on_captured)
        self.capturer.failed.connect(self._on_capture_failed)

        self.server = CommandServer(self)
        self.server.command_received.connect(self.handle_command)

        self.init_ui(show_welcome)

    def init_ui(self, show_welcome):
        # 1. Tray Icon yaratish
        self.tray_icon = QSystemTrayIcon(self)

        # Tizimning standart 'camera' belgisini olamiz (rasm qidirib o'tirmaslik uchun)
        icon = QIcon.fromTheme("camera-photo")
        if icon.isNull():
            # Agar tizim belgisi topilmasa, shunchaki bo'sh belgi (yoki o'z rasmingizni qo'ying)
            icon = QIcon.fromTheme("applications-graphics")

        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip(f"MyShot {__version__}")

        # 2. Menyu yaratish (O'ng tugma bosilganda chiqadigan)
        self.menu = QMenu()

        # Action: Hududni belgilab olish (Lightshot style)
        select_action = QAction("✂️ Capture area", self)
        select_action.triggered.connect(lambda: self.take_area_screenshot(MENU_CLOSE_DELAY_MS))
        self.menu.addAction(select_action)

        # Action: To'liq ekran
        full_action = QAction("🖥️ Capture full screen", self)
        full_action.triggered.connect(lambda: self.take_full_screenshot(MENU_CLOSE_DELAY_MS))
        self.menu.addAction(full_action)

        self.menu.addSeparator()

        # Action: Klaviatura yorlig'ini o'rnatish
        shortcut_action = QAction(f"⌨️ Install shortcut ({AREA_BINDING})", self)
        shortcut_action.triggered.connect(self.install_shortcut)
        self.menu.addAction(shortcut_action)

        # Ajratuvchi chiziq
        self.menu.addSeparator()

        # Action: Chiqish
        quit_action = QAction("❌ Quit", self)
        quit_action.triggered.connect(QApplication.instance().quit)
        self.menu.addAction(quit_action)

        # Menuni trayga ulash
        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.show()

        # Dastur ishga tushganda bildirishnoma ko'rsatish
        # (buyruq bilan ishga tushganda ko'rsatmaymiz – aks holda rasmga tushib qoladi)
        if show_welcome:
            self.notify("MyShot", "MyShot is running. Use the tray icon near the clock.", 2000)

    def notify(self, title, message, msecs=4000):
        self.tray_icon.showMessage(title, message, QSystemTrayIcon.MessageIcon.NoIcon, msecs)

    # --- buyruqlar ------------------------------------------------------

    def handle_command(self, command):
        if command == "area":
            self.take_area_screenshot()
        elif command == "full":
            self.take_full_screenshot()

    def take_area_screenshot(self, delay_ms=0):
        self._start_capture("area", delay_ms)

    def take_full_screenshot(self, delay_ms=0):
        self._start_capture("full", delay_ms)

    def _start_capture(self, mode, delay_ms):
        # Oldingi rasmga olish hali tugamagan bo'lsa, yangisini boshlamaymiz
        if self._pending or self._session:
            return
        self._pending = mode
        QTimer.singleShot(delay_ms, self.capturer.capture)

    # --- natijalar ------------------------------------------------------

    def _on_captured(self, image):
        mode, self._pending = self._pending, None
        if mode == "full":
            filepath = get_save_path()
            if image.save(filepath, "PNG"):
                self.notify("Saved", filepath)
            else:
                self.notify("Error", "Could not save the screenshot")
            return

        self._session = CaptureSession(image, get_save_path, self)
        self._session.finished.connect(self._on_session_finished)
        self._session.start()

    def _on_capture_failed(self, message):
        self._pending = None
        self.notify("Capture failed", message)

    def _on_session_finished(self, action, filepath):
        self._session.deleteLater()
        self._session = None
        if action == "save":
            self.notify("Saved", filepath)
        elif action == "copy":
            self.notify("Copied", "Screenshot copied to clipboard")
        elif action == "error":
            self.notify("Error", "Could not save the screenshot")

    def install_shortcut(self):
        try:
            freed = install_area_shortcut()
        except HotkeyError as error:
            self.notify("Shortcut not installed", str(error))
            return
        message = f"{AREA_BINDING} now starts area capture."
        if freed:
            message += f"\nRemoved from GNOME shortcuts: {', '.join(freed)}"
        self.notify("Shortcut installed", message)


def run(initial_command=None):
    # Qt tsikli ishlayotganda Python SIGINT'ni ushlay olmaydi – Ctrl+C dasturni darhol yopsin
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv[:1])
    app.setApplicationName("MyShot")
    app.setApplicationVersion(__version__)
    # Ubuntu oynani yopganda dastur o'chib ketmasligi uchun
    app.setQuitOnLastWindowClosed(False)

    tray = ScreenshotTrayApp(show_welcome=initial_command is None)
    if initial_command:
        QTimer.singleShot(0, lambda: tray.handle_command(initial_command))
    return app.exec()
