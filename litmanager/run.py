"""
run.py
------
Entry point for both `python run.py` (development) and the packaged .exe.

Starts the local Flask server on 127.0.0.1 (never exposed to the network)
and opens it in the user's default browser, so it behaves like a desktop
app without needing Electron/Tauri packaging.
"""

import os
import sys
import threading
import webbrowser
import time

# Make sure the app package is importable whether run as a script or a
# PyInstaller-frozen executable.
if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS  # PyInstaller temp extraction dir
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from app.app import app, create_app  # noqa: E402

HOST = "127.0.0.1"
PORT = 5001


def open_browser():
    time.sleep(1.0)
    webbrowser.open(f"http://{HOST}:{PORT}/")


def main():
    daemon_mode = "--daemon" in sys.argv
    create_app()
    if not daemon_mode:
        threading.Thread(target=open_browser, daemon=True).start()
    print(f"Personal Literature Manager running at http://{HOST}:{PORT}")
    if daemon_mode:
        print("Running in background daemon mode.")
    print("Close this window (or press Ctrl+C) to stop the app.")
    
    # We must run debug=False or else it spawns a reloader process which can break sys.argv forwarding
    app.run(host=HOST, port=PORT, debug=False)


if __name__ == "__main__":
    main()
