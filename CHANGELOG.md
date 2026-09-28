# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-09-28

### Added
- Annotation tools on the selected area: pen, line, arrow, rectangle, ellipse,
  marker (highlighter) and text. Tool shortcuts: `P`, `L`, `A`, `R`, `E`, `M`, `T`.
- Vertical tool bar next to the selection with color picker (8 presets and a
  custom color dialog) and line width slider.
- Mouse wheel changes the line width; `Shift` snaps lines/arrows to 45° and
  makes rectangles/ellipses square.
- Undo / redo (`Ctrl+Z`, `Ctrl+Shift+Z` / `Ctrl+Y`).
- The last used color and width are remembered.
- Annotations are rendered at full resolution on HiDPI screens.

### Changed
- All user interface texts are now in English.
- Clicking outside the selection no longer discards it once something is drawn.

## [0.2.1] - 2026-09-28

### Fixed
- `Ctrl+C` in the terminal now quits the app (Qt event loop swallowed SIGINT).
- Commands (`--area`, `--full`) were silently lost when the running instance was
  suspended or frozen; the instance now acknowledges each command, and a new
  launch takes over if no acknowledgement arrives.

## [0.2.0] - 2026-09-28

### Added
- Lightshot-style area selection: the screen is frozen, the selected area gets a
  frame with 8 resize handles, can be moved, and shows its size in pixels.
- Action bar next to the selection: **Save** (`Ctrl+S` / `Enter`),
  **Copy to clipboard** (`Ctrl+C`), **Cancel** (`Esc` / right click).
- Multi-monitor support (one overlay per screen) and HiDPI-aware cropping.
- Command line interface: `--area`, `--full`, `--install-shortcut`, `--version`.
- Single instance: a running tray app receives commands over a local socket,
  so a keyboard shortcut can trigger capture instantly.
- Global keyboard shortcut via GNOME custom keybindings (`Shift+Print` → area);
  can be installed from the tray menu or with `--install-shortcut`.
- Screen capture engine: Qt on X11, XDG Desktop Portal on Wayland,
  `gnome-screenshot` as a fallback.

### Changed
- The whole screen is captured *before* the selection UI appears, so open menus
  and popups of other applications stay in the screenshot.
- Capturing no longer blocks the UI (`os.system` replaced).
- `run.sh` works from any directory and forwards arguments.

## [0.1.0] - 2026-09-28

### Added
- System tray app with area and full screen capture via `gnome-screenshot`.
- Auto-save to `~/Pictures/Screenshots` and desktop notifications.

[Unreleased]: https://github.com/OnlineAzamat/myshot-linux-app/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/OnlineAzamat/myshot-linux-app/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/OnlineAzamat/myshot-linux-app/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/OnlineAzamat/myshot-linux-app/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/OnlineAzamat/myshot-linux-app/releases/tag/v0.1.0
