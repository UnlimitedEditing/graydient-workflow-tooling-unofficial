"""
Graydient Studio Desktop Launcher.
Starts the local studio server and opens the native-style desktop app window.
"""

import os
import sys
import time
import argparse
import webbrowser
import subprocess
from pathlib import Path

STUDIO_DIR = Path(__file__).resolve().parent

def open_desktop_window(url: str):
    """Attempts to open in standalone app mode via Edge/Chrome, falling back to default browser."""
    # Common browser paths on Windows
    edge_paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]

    for p in edge_paths + chrome_paths:
        if os.path.exists(p):
            try:
                subprocess.Popen([p, f"--app={url}"])
                print(f"🚀 Opened native desktop app window via {os.path.basename(p)}")
                return
            except Exception:
                pass

    # Fallback to standard web browser
    webbrowser.open(url)
    print(f"🚀 Opened in default web browser: {url}")

def main():
    parser = argparse.ArgumentParser(description="Graydient Studio — Desktop Application")
    parser.add_argument("--port", type=int, default=8765, help="Port to run Studio server on (default 8765)")
    parser.add_argument("--host", default="127.0.0.1", help="Host address (default 127.0.0.1)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically launch browser window")
    args = parser.parse_args()

    # Add repo root to python path
    sys.path.insert(0, str(STUDIO_DIR))

    url = f"http://{args.host}:{args.port}"
    print("=" * 65)
    print("  [*] GRAYDIENT STUDIO -- UNIFIED WORKFLOW & M3DS DESKTOP SUITE")
    print("=" * 65)
    print(f"  * Studio UI:        {url}")
    print(f"  * AI Engine:        Google Gemini 2.0 Flash (1M Context)")
    print(f"  * M3DS Converter:   Active (GLB / PLY / Score JSON)")
    print(f"  * Zero-Defect Lint: 25+ Pre-Flight Checks (KI-001..KI-009)")
    print("=" * 65)

    if not args.no_browser:
        import threading
        def _delayed_launch():
            time.sleep(1.2)
            open_desktop_window(url)
        t = threading.Thread(target=_delayed_launch, daemon=True)
        t.start()

    import uvicorn
    uvicorn.run("studio.server:app", host=args.host, port=args.port, log_level="info")

if __name__ == "__main__":
    main()
