"""Single-instance guard via a named Windows kernel mutex.

Call ``acquire()`` once at startup. If a mutex with the same name is already
held by another process, this call returns False and the caller should exit.
"""

from __future__ import annotations

import sys


_mutex_handle = None  # kept alive for the process lifetime
_MUTEX_NAME = "Global\\StarlightFilter_SingleInstance_Mutex_v1"
_ERROR_ALREADY_EXISTS = 183


def acquire() -> bool:
    global _mutex_handle
    if sys.platform != "win32":
        return True
    import ctypes

    _mutex_handle = ctypes.windll.kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    if not _mutex_handle:
        return True  # can't create it either — don't block startup
    return ctypes.windll.kernel32.GetLastError() != _ERROR_ALREADY_EXISTS
