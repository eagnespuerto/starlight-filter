"""System-tray icon backed by pystray.

Runs pystray on a daemon thread; menu callbacks marshal back to the Tk main
thread via a caller-supplied ``schedule`` function (typically ``root.after``).
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

import pystray
from PIL import Image


def start_tray(
    icon_path: Path,
    schedule: Callable[[Callable[[], None]], None],
    on_show: Callable[[], None],
    on_reset: Callable[[], None],
    on_toggle_autostart: Callable[[], None],
    autostart_is_enabled: Callable[[], bool],
    on_quit: Callable[[], None],
) -> pystray.Icon:
    """Create and start the tray icon on a daemon thread. Returns the Icon.

    ``schedule`` is called from the tray thread with a zero-arg callable that
    must run on the Tk main thread. Typically ``lambda cb: root.after(0, cb)``.
    """
    image = Image.open(icon_path)

    def marshal(target: Callable[[], None]):
        def handler(_icon, _item=None):
            schedule(target)
        return handler

    def autostart_handler(_icon, _item):
        schedule(on_toggle_autostart)

    menu = pystray.Menu(
        pystray.MenuItem("Show", marshal(on_show), default=True),
        pystray.MenuItem("Reset gamma", marshal(on_reset)),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            "Start with Windows",
            autostart_handler,
            checked=lambda _item: autostart_is_enabled(),
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", marshal(on_quit)),
    )
    icon = pystray.Icon("StarlightFilter", image, "Starlight Filter", menu)

    thread = threading.Thread(target=icon.run, daemon=True)
    thread.start()
    return icon
