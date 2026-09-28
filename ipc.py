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


ACK = b"ok\n"


def send_command(command, timeout=1.0):
    """Ishlab turgan nusxa buyruqni qabul qilib, tasdiqlasa True qaytaradi.

    Tasdiq kutilishi muhim: to'xtatilgan (Ctrl+Z) yoki osilib qolgan nusxa ham
    socket'ni ochiq ushlab turadi, lekin buyruqni bajarmaydi.
    """
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect(SOCKET_PATH)
            sock.sendall(f"{command}\n".encode())
            return sock.recv(len(ACK)) == ACK
    except OSError:
        return False
