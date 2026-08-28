"""Windows sign-in autostart via HKCU\\...\\Run.

Public surface: is_enabled(), enable(), disable(). All no-ops off Windows.
"""

from __future__ import annotations

import sys
from pathlib import Path


APP_KEY = "StarlightFilter"
_RUN_SUBKEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _autostart_command() -> str:
    """Command line Windows should run on sign-in.

    Includes ``--minimized`` so the app starts hidden in the tray, not as a
    popup window every login.
    """
    if getattr(sys, "frozen", False):
        # PyInstaller-bundled .exe: run the exe itself.
        exe = sys.executable
        return f'"{exe}" --minimized'
    # Running from source: prefer pythonw so no console flashes on sign-in.
    py = sys.executable
    if py.lower().endswith("python.exe"):
        py = py[: -len("python.exe")] + "pythonw.exe"
    run_py = Path(__file__).resolve().parent.parent / "run.py"
    return f'"{py}" "{run_py}" --minimized'


def is_enabled() -> bool:
    if sys.platform != "win32":
        return False
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_SUBKEY, 0, winreg.KEY_QUERY_VALUE
        ) as key:
            winreg.QueryValueEx(key, APP_KEY)
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def enable() -> bool:
    if sys.platform != "win32":
        return False
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_SUBKEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, APP_KEY, 0, winreg.REG_SZ, _autostart_command())
        return True
    except OSError:
        return False


def disable() -> bool:
    if sys.platform != "win32":
        return False
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_SUBKEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            try:
                winreg.DeleteValue(key, APP_KEY)
            except FileNotFoundError:
                pass
        return True
    except OSError:
        return False
