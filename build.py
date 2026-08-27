"""Build a standalone Windows .exe with PyInstaller.

Usage:
    python build.py

Writes ``dist/StarlightFilter.exe``.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ICON = ROOT / "assets" / "icon.ico"


def ensure_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
        return
    except ImportError:
        pass
    print("PyInstaller not found — installing into the current environment...")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "pyinstaller"]
    )


def build() -> Path:
    ensure_pyinstaller()

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--windowed",
        "--name",
        "StarlightFilter",
        "--noconfirm",
        "--clean",
    ]
    if ICON.exists():
        cmd += ["--icon", str(ICON)]
    else:
        print(f"(no icon at {ICON}; building without one)")
    cmd += [str(ROOT / "run.py")]

    print("Running:", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)

    exe = ROOT / "dist" / "StarlightFilter.exe"
    if not exe.exists():
        raise SystemExit(f"Build finished but {exe} not found.")
    print(f"\nBuilt: {exe}")
    return exe


if __name__ == "__main__":
    build()
