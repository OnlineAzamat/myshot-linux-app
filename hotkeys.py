"""GNOME'da MyShot uchun global klaviatura yorlig'ini sozlash.

Wayland'da dastur o'zi global tugmani ushlay olmaydi, shuning uchun GNOME'ning
"maxsus yorliqlar" (custom keybindings) mexanizmidan foydalanamiz: tugma
bosilganda GNOME `myshot.py --area` buyrug'ini ishga tushiradi.
"""
import ast
import os
import shlex
import shutil
import subprocess
import sys

MEDIA_KEYS = "org.gnome.settings-daemon.plugins.media-keys"
CUSTOM_SCHEMA = MEDIA_KEYS + ".custom-keybinding"
CUSTOM_BASE = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/"
# GNOME'ning o'z screenshot tugmalari – bir xil tugma ikki joyda bo'lsa, GNOME'niki ustun keladi
SHELL_KEYS = "org.gnome.shell.keybindings"
SHELL_SCREENSHOT_KEYS = ("show-screenshot-ui", "screenshot", "screenshot-window")

AREA_BINDING = "<Shift>Print"
SCRIPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "myshot.py")


class HotkeyError(Exception):
    pass


def _gsettings(*args):
    try:
        result = subprocess.run(["gsettings", *args], capture_output=True, text=True, check=True)
    except FileNotFoundError:
        raise HotkeyError("gsettings not found (is GNOME installed?)")
    except subprocess.CalledProcessError as error:
        raise HotkeyError(error.stderr.strip() or str(error))
    return result.stdout.strip()


def _gvariant_str(value):
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _parse_strv(text):
    text = text.removeprefix("@as").strip()
    return list(ast.literal_eval(text)) if text else []


def _format_strv(values):
    return "[" + ", ".join(_gvariant_str(v) for v in values) + "]"


def launch_command(action):
    return shlex.join([sys.executable, SCRIPT_PATH, f"--{action}"])


def _free_shell_binding(binding):
    """Tugmani GNOME'ning screenshot yorliqlaridan olib tashlaydi, o'zgargan kalitlarni qaytaradi."""
    freed = []
    for key in SHELL_SCREENSHOT_KEYS:
        try:
            current = _parse_strv(_gsettings("get", SHELL_KEYS, key))
        except (HotkeyError, ValueError, SyntaxError):
            continue
        remaining = [b for b in current if b.lower() != binding.lower()]
        if remaining != current:
            _gsettings("set", SHELL_KEYS, key, _format_strv(remaining))
            freed.append(key)
    return freed


def install_area_shortcut(binding=AREA_BINDING):
    """Maydonni belgilash yorlig'ini o'rnatadi. GNOME'dan bo'shatilgan kalitlar ro'yxatini qaytaradi."""
    if not shutil.which("gsettings"):
        raise HotkeyError("gsettings not found (is GNOME installed?)")

    path = CUSTOM_BASE + "myshot-area/"
    paths = _parse_strv(_gsettings("get", MEDIA_KEYS, "custom-keybindings"))
    if path not in paths:
        paths.append(path)
        _gsettings("set", MEDIA_KEYS, "custom-keybindings", _format_strv(paths))

    schema = f"{CUSTOM_SCHEMA}:{path}"
    _gsettings("set", schema, "name", _gvariant_str("MyShot – capture area"))
    _gsettings("set", schema, "command", _gvariant_str(launch_command("area")))
    _gsettings("set", schema, "binding", _gvariant_str(binding))
    return _free_shell_binding(binding)
