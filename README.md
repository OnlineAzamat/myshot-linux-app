# MyShot 📸

A lightweight, system-tray based screenshot utility for Linux (GNOME/Ubuntu), built with Python and PyQt6.

## Features

- **System Tray Integration**: Runs quietly in the background without cluttering your taskbar.
- **Area Selection**: Select a specific part of your screen to capture (similar to Lightshot).
- **Full Screen Capture**: Quickly grab the entire screen.
- **Auto-Save**: Screenshots are automatically saved to `~/Pictures/Screenshots` with timestamps.
- **System Notifications**: Get a desktop notification as soon as your shot is saved.
- **Modern UI**: Simple and intuitive tray menu.

## Prerequisites

This tool relies on `gnome-screenshot` for the capture engine. Ensure it is installed on your system:

```bash
sudo apt update
sudo apt install gnome-screenshot
```

## Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/myshot.git
   cd myshot
   ```

2. **Set up a virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install PyQt6
   ```

## Usage

You can start the application using the provided run script:

```bash
./run.sh
```

Or run it directly via the virtual environment:

```bash
./venv/bin/python3 myshot.py
```

Once started, look for the camera icon in your system tray (near the clock). Right-click it to access the capture options.

## Project Structure

- `myshot.py`: Main application logic.
- `run.sh`: Helper script to launch the app.
- `venv/`: Local Python environment.

## License

This project is open-source and available under the [MIT License](LICENSE).
