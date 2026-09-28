#!/usr/bin/env python3
"""MyShot – kirish nuqtasi.

    myshot.py                     tray ilovasini ishga tushiradi
    myshot.py --area              maydonni belgilash (klaviatura yorlig'i uchun)
    myshot.py --full              to'liq ekranni saqlash
    myshot.py --install-shortcut  GNOME'da Shift+PrtScr yorlig'ini o'rnatish

Dastur allaqachon ishlab turgan bo'lsa, buyruq unga yuboriladi va bu jarayon
darhol tugaydi. PyQt faqat kerak bo'lganda yuklanadi – shunda yorliq tez ishlaydi.
"""
import argparse
import sys

from ipc import send_command
from version import __version__


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="myshot", description="Lightshot-style screenshot tool")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--area", dest="command", action="store_const", const="area",
                       help="select an area and capture it")
    group.add_argument("--full", dest="command", action="store_const", const="full",
                       help="capture the full screen")
    group.add_argument("--install-shortcut", dest="command", action="store_const",
                       const="install-shortcut", help="install the GNOME keyboard shortcut")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser.parse_args(argv)


def main():
    args = parse_args(sys.argv[1:])

    if args.command == "install-shortcut":
        from hotkeys import AREA_BINDING, HotkeyError, install_area_shortcut
        try:
            freed = install_area_shortcut()
        except HotkeyError as error:
            print(f"Error: {error}", file=sys.stderr)
            return 1
        print(f"Shortcut installed: {AREA_BINDING} → capture area")
        if freed:
            print(f"Removed from GNOME shortcuts: {', '.join(freed)}")
        return 0

    if args.command and send_command(args.command):
        return 0

    from app import run
    return run(args.command)


if __name__ == "__main__":
    sys.exit(main())
