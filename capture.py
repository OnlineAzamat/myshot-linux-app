"""Butun ekranni (barcha monitorlarni) bitta QImage sifatida olish.

Tartib:
  * X11      – Qt orqali to'g'ridan-to'g'ri (eng tez);
  * Wayland  – gnome-screenshot (GNOME Shell uni ruxsat berilganlar ro'yxatida saqlaydi);
  * zaxira   – XDG Desktop Portal (org.freedesktop.portal.Screenshot).

Nega portal asosiy emas: GNOME 46 portal'i birinchi so'rovda ruxsat oynasini
faqat fokusdagi ilovaga ko'rsatadi, tray ilovasi esa hech qachon fokusda
bo'lmaydi – natijada so'rov rad etiladi.
"""
import os
import shutil
import tempfile
import uuid
from urllib.parse import unquote, urlparse

from PyQt6.QtCore import (QObject, QProcess, QProcessEnvironment, QRect, QRectF, Qt, QTimer,
                          pyqtSignal, pyqtSlot)
from PyQt6.QtDBus import QDBus, QDBusConnection, QDBusMessage
from PyQt6.QtGui import QGuiApplication, QImage, QPainter

PORTAL_SERVICE = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"
SCREENSHOT_IFACE = "org.freedesktop.portal.Screenshot"
REQUEST_IFACE = "org.freedesktop.portal.Request"
# Birinchi marta GNOME ruxsat so'rashi mumkin, foydalanuvchiga vaqt beramiz
PORTAL_TIMEOUT_MS = 30000


def virtual_geometry(screens):
    """Barcha monitorlarni qamrab oluvchi to'rtburchak (mantiqiy koordinatalarda)."""
    geometry = QRect()
    for screen in screens:
        geometry = geometry.united(screen.geometry())
    return geometry


class ScreenCapturer(QObject):
    captured = pyqtSignal(QImage)
    failed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._busy = False
        self._request_path = None
        self._timeout = QTimer(self)
        self._timeout.setSingleShot(True)
        self._timeout.timeout.connect(self._on_portal_timeout)

    def is_busy(self):
        return self._busy

    def capture(self):
        if self._busy:
            return
        self._busy = True
        if QGuiApplication.platformName() == "xcb":
            self._grab_with_qt()
        elif shutil.which("gnome-screenshot"):
            self._grab_with_gnome_screenshot()
        elif not self._request_portal():
            self._fail("gnome-screenshot is not installed and the portal is unavailable")

    # --- natija ---------------------------------------------------------

    def _finish(self, image):
        self._busy = False
        if image.isNull():
            self.failed.emit("Could not read the screenshot")
        else:
            self.captured.emit(image)

    def _fail(self, message):
        self._busy = False
        self.failed.emit(message)

    def _finish_from_file(self, path):
        image = QImage(path)
        try:
            os.remove(path)
        except OSError:
            pass
        self._finish(image)

    # --- X11 ------------------------------------------------------------

    def _grab_with_qt(self):
        screens = QGuiApplication.screens()
        virtual = virtual_geometry(screens)
        scale = max(screen.devicePixelRatio() for screen in screens)
        image = QImage(round(virtual.width() * scale), round(virtual.height() * scale),
                       QImage.Format.Format_RGB32)
        image.fill(Qt.GlobalColor.black)
        painter = QPainter(image)
        for screen in screens:
            pixmap = screen.grabWindow(0)
            g = screen.geometry().translated(-virtual.topLeft())
            target = QRectF(g.x() * scale, g.y() * scale, g.width() * scale, g.height() * scale)
            painter.drawPixmap(target, pixmap, QRectF(pixmap.rect()))
        painter.end()
        self._finish(image)

    # --- Wayland: XDG Desktop Portal -----------------------------------

    def _request_portal(self):
        bus = QDBusConnection.sessionBus()
        if not bus.isConnected():
            return False

        # Javob signaliga so'rov yuborilishidan OLDIN obuna bo'lamiz (race bo'lmasligi uchun)
        token = "myshot_" + uuid.uuid4().hex
        sender = bus.baseService().lstrip(":").replace(".", "_")
        self._request_path = f"{PORTAL_PATH}/request/{sender}/{token}"
        if not bus.connect("", self._request_path, REQUEST_IFACE, "Response",
                           self._on_portal_response):
            self._request_path = None
            return False

        message = QDBusMessage.createMethodCall(PORTAL_SERVICE, PORTAL_PATH,
                                                SCREENSHOT_IFACE, "Screenshot")
        message.setArguments(["", {"handle_token": token, "interactive": False}])
        reply = bus.call(message, QDBus.CallMode.Block, 5000)
        if reply.type() == QDBusMessage.MessageType.ErrorMessage:
            self._disconnect_portal()
            return False

        self._timeout.start(PORTAL_TIMEOUT_MS)
        return True

    def _disconnect_portal(self):
        if self._request_path:
            QDBusConnection.sessionBus().disconnect("", self._request_path, REQUEST_IFACE,
                                                    "Response", self._on_portal_response)
        self._request_path = None
        self._timeout.stop()

    @pyqtSlot(QDBusMessage)
    def _on_portal_response(self, message):
        self._disconnect_portal()
        args = message.arguments()
        response = int(args[0]) if args else 2
        results = args[1] if len(args) > 1 else {}

        if response == 1:
            self._fail("Screenshot permission denied")
            return
        uri = results.get("uri") if response == 0 else None
        if hasattr(uri, "variant"):
            uri = uri.variant()
        if not uri:
            self._fail("The portal returned no image")
            return
        # Portal faylni ~/Pictures ichiga saqlaydi, uni o'qib bo'lgach o'chiramiz
        self._finish_from_file(unquote(urlparse(uri).path))

    def _on_portal_timeout(self):
        self._disconnect_portal()
        self._fail("The portal did not respond")

    # --- Wayland: gnome-screenshot --------------------------------------

    @staticmethod
    def _clean_environment():
        """Snap ilovalaridan (masalan VS Code) meros qolgan GTK yo'llarini olib tashlaydi –
        ular bilan gnome-screenshot 'symbol lookup error' bilan yiqiladi."""
        env = QProcessEnvironment.systemEnvironment()
        for key in env.keys():
            value = env.value(key)
            if "/snap/" not in value:
                continue
            if key in ("PATH", "XDG_DATA_DIRS"):
                env.insert(key, ":".join(p for p in value.split(":") if "/snap/" not in p))
            else:
                env.remove(key)
        return env

    def _grab_with_gnome_screenshot(self):
        fd, path = tempfile.mkstemp(prefix="myshot-", suffix=".png")
        os.close(fd)
        process = QProcess(self)
        process.setProcessEnvironment(self._clean_environment())

        def on_finished(*_):
            process.deleteLater()
            self._finish_from_file(path)

        def on_error(error):
            if error == QProcess.ProcessError.FailedToStart:
                process.deleteLater()
                os.remove(path)
                self._fail("gnome-screenshot not found")

        process.finished.connect(on_finished)
        process.errorOccurred.connect(on_error)
        process.start("gnome-screenshot", ["-f", path])
