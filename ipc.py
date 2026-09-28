"""Ishlab turgan MyShot nusxasiga buyruq yuborish.

Bu modul ataylab faqat standart kutubxonadan foydalanadi: klaviatura yorlig'i
bosilganda `myshot.py --area` PyQt'ni yuklamasdan buyruqni tezda yetkazib,
darhol chiqib ketadi. Shunda ekrandagi menyular yopilib ulgurmaydi.
"""
import os
import socket


def _socket_path():
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
    return os.path.join(runtime_dir, f"myshot-{os.getuid()}.sock")


SOCKET_PATH = _socket_path()


def send_command(command, timeout=0.5):
    """Buyruq ishlab turgan nusxaga yetkazilsa True qaytaradi."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect(SOCKET_PATH)
            sock.sendall(f"{command}\n".encode())
        return True
    except OSError:
        return False
