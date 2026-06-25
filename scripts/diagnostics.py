#!/usr/bin/env python3
"""Standalone diagnostics: checks printer detection, label config, USB access,
and font file presence. Run with: python -m scripts.diagnostics"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.printer import detect_printer  # noqa: E402


def main() -> int:
    settings = get_settings()
    ok = True

    print(f"Printer model:       {settings.default_printer_model}")
    print(f"Label width (mm):    {settings.default_label_width_mm}")
    print(f"USB backend:         {settings.usb_backend}")
    print(f"Printer identifier:  {settings.printer_identifier or '(autodetect)'}")
    print()

    print("Detecting USB printers...")
    devices = detect_printer(settings.usb_backend)
    if devices:
        for d in devices:
            print(f"  found: {d}")
    else:
        print("  no printers detected (check USB cable/power, or pyusb permissions)")
        ok = False
    print()

    font_dir = Path(settings.font_dir)
    print(f"Font directory: {font_dir}")
    required_fonts = ["DejaVuSans.ttf", "DejaVuSans-Bold.ttf"]
    for name in required_fonts:
        path = font_dir / name
        status = "OK" if path.is_file() else "MISSING"
        if status == "MISSING":
            ok = False
        print(f"  {name}: {status}")
    print()

    for path_str, label in (
        (settings.preview_dir, "preview_dir"),
        (settings.log_dir, "log_dir"),
        (str(Path(settings.db_path).parent), "db_path parent"),
    ):
        path = Path(path_str)
        writable = path.exists() and path.is_dir()
        print(f"{label}: {path} -> {'OK' if writable else 'MISSING (will be created on startup)'}")

    print()
    print("Diagnostics: " + ("PASS" if ok else "ISSUES FOUND"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
