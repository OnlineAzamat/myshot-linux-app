# MyShot 📸

A lightweight, system-tray based screenshot utility for Linux (GNOME/Ubuntu), built with Python and PyQt6.
Inspired by Lightshot.

## Features

- **System Tray Integration**: Runs quietly in the background without cluttering your taskbar.
- **Lightshot-style Area Selection**: The screen freezes, you draw a frame, then move or
  resize it with handles. Nothing is saved until you press **Save** or **Copy**.
- **Keyboard Shortcut**: `Shift+PrtScr` opens area selection instantly, so open menus and
  right-click popups of other apps stay in the screenshot.
- **Full Screen Capture**: Quickly grab the entire screen.
- **Clipboard**: Copy the selected area with `Ctrl+C`.
- **Auto-Save**: Screenshots are saved to `~/Pictures/Screenshots` with timestamps.
- **Multi-monitor & HiDPI** aware.
- Works on both **Wayland** (via XDG Desktop Portal) and **X11**.

## Prerequisites

- GNOME desktop (Ubuntu 22.04+ recommended)
- Python 3.10+
- `gnome-screenshot` (optional, used only as a fallback):
  ```bash
  sudo apt install gnome-screenshot
  ```

## Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/OnlineAzamat/myshot-linux-app.git
   cd myshot-linux-app
   ```

2. **Set up a virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Install the keyboard shortcut** (once):
   ```bash
   ./run.sh --install-shortcut
   ```
   or use *⌨️ Yorliq o'rnatish* from the tray menu.

## Usage

Start the tray application:

```bash
./run.sh
```

Command line options:

| Command                        | Action                                  |
| ------------------------------ | --------------------------------------- |
| `./run.sh`                     | Start the tray app                      |
| `./run.sh --area`              | Select an area (used by the shortcut)   |
| `./run.sh --full`              | Save the full screen                    |
| `./run.sh --install-shortcut`  | Bind `Shift+PrtScr` in GNOME            |
| `./run.sh --version`           | Show version                            |

If the tray app is already running, `--area` / `--full` are forwarded to it.

### Selection controls

| Key / mouse                 | Action                         |
| --------------------------- | ------------------------------ |
| Drag                        | Select an area                 |
| Drag inside / on handles    | Move / resize the selection    |
| `Ctrl+S`, `Enter`           | Save                           |
| `Ctrl+C`                    | Copy to clipboard              |
| `Esc`, right click          | Cancel                         |

> **Wayland note:** the first capture may show a GNOME dialog asking to allow
> screenshots. Choose *Allow* – it will not be asked again.

## Project Structure

- `myshot.py` – entry point and command line interface.
- `app.py` – tray icon, menu and command server.
- `capture.py` – full screen capture (Qt / XDG portal / gnome-screenshot).
- `overlay.py` – Lightshot-style selection overlay.
- `hotkeys.py` – GNOME keyboard shortcut setup.
- `ipc.py` – sends commands to the running instance.
- `version.py` – application version.

## Versioning

MyShot follows [Semantic Versioning](https://semver.org/). Releases are tagged as
`vX.Y.Z`; see [CHANGELOG.md](CHANGELOG.md) for details.

## License

This project is open-source and available under the [MIT License](LICENSE).
