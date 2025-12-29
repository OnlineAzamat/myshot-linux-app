import sys
import os
from datetime import datetime
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox, QWidget
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import QProcess

class ScreenshotTrayApp(QWidget):
    def __init__(self):
        super().__init__()
        
        # Dastur oynasini yashiramiz (bizga faqat tray kerak)
        self.hide()
        
        self.init_ui()

    def init_ui(self):
        # 1. Tray Icon yaratish
        self.tray_icon = QSystemTrayIcon(self)
        
        # Tizimning standart 'camera' belgisini olamiz (rasm qidirib o'tirmaslik uchun)
        icon = QIcon.fromTheme("camera-photo")
        if icon.isNull():
            # Agar tizim belgisi topilmasa, shunchaki bo'sh belgi (yoki o'z rasmingizni qo'ying)
            icon = QIcon.fromTheme("applications-graphics")
            
        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip("Meniń Screenshot Programmam")

        # 2. Menyu yaratish (O'ng tugma bosilganda chiqadigan)
        menu = QMenu()

        # Action: Hududni belgilab olish (Lightshot style)
        select_action = QAction("✂️ Maydandi tanlaw (Area)", self)
        select_action.triggered.connect(self.take_area_screenshot)
        menu.addAction(select_action)

        # Action: To'liq ekran
        full_action = QAction("🖥️ Toliq ekran", self)
        full_action.triggered.connect(self.take_full_screenshot)
        menu.addAction(full_action)

        # Ajratuvchi chiziq
        menu.addSeparator()

        # Action: Chiqish
        quit_action = QAction("❌ Shigiw", self)
        quit_action.triggered.connect(QApplication.instance().quit)
        menu.addAction(quit_action)

        # Menuni trayga ulash
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()

        # Dastur ishga tushganda bildirishnoma ko'rsatish
        self.tray_icon.showMessage(
            "Screenshot Dasturi",
            "Dastur ishga tushdi! Tray (soat yoni)dan foydalaning.",
            QSystemTrayIcon.MessageIcon.Information,
            2000
        )

    def get_save_path(self):
        # Fayl nomini va yo'lini generatsiya qilish
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        save_dir = os.path.expanduser("~/Pictures/Screenshots")
        os.makedirs(save_dir, exist_ok=True)
        return os.path.join(save_dir, f"shot_{timestamp}.png")

    def take_area_screenshot(self):
        # Hududni tanlab olish (-a bayrog'i area selection uchun)
        filepath = self.get_save_path()
        # Buyruqni ishga tushiramiz
        # Waylandda bu sichqonchani krestik (+) ga aylantiradi
        cmd = f"gnome-screenshot -a -f {filepath}"
        os.system(cmd)
        
        # Agar fayl paydo bo'lsa, demak rasm olindi
        if os.path.exists(filepath):
            self.tray_icon.showMessage("Saqlandi!", f"Manzil: {filepath}", QSystemTrayIcon.MessageIcon.NoIcon)

    def take_full_screenshot(self):
        # To'liq ekran
        filepath = self.get_save_path()
        cmd = f"gnome-screenshot -f {filepath}"
        os.system(cmd)
        
        if os.path.exists(filepath):
            self.tray_icon.showMessage("Saqlandi!", f"Manzil: {filepath}", QSystemTrayIcon.MessageIcon.NoIcon)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    # Ubuntu oynani yopganda dastur o'chib ketmasligi uchun
    app.setQuitOnLastWindowClosed(False)
    
    ex = ScreenshotTrayApp()
    sys.exit(app.exec())