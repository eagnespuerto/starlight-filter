"""Thin ctypes wrapper over the Win32 gamma-ramp API.

Public surface: capture_original, apply, restore, is_supported.
Nothing else in the codebase imports ctypes.
"""

from __future__ import annotations

import sys
from typing import Optional


_supported: bool = False
_original = None  # ctypes ramp buffer set by capture_original()


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _gdi32 = ctypes.windll.gdi32
    _user32 = ctypes.windll.user32
    _shell32 = ctypes.windll.shell32

    def set_app_user_model_id(app_id: str) -> None:
        """Tell Windows this process is its own app so the taskbar picks up our icon."""
        try:
            _shell32.SetCurrentProcessExplicitAppUserModelID(ctypes.c_wchar_p(app_id))
        except (AttributeError, OSError):
            pass

    _GetDC = _user32.GetDC
    _GetDC.restype = wintypes.HDC
    _GetDC.argtypes = [wintypes.HWND]

    _ReleaseDC = _user32.ReleaseDC
    _ReleaseDC.restype = ctypes.c_int
    _ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]

    _GetDeviceGammaRamp = _gdi32.GetDeviceGammaRamp
    _GetDeviceGammaRamp.restype = wintypes.BOOL
    _GetDeviceGammaRamp.argtypes = [wintypes.HDC, ctypes.c_void_p]

    _SetDeviceGammaRamp = _gdi32.SetDeviceGammaRamp
    _SetDeviceGammaRamp.restype = wintypes.BOOL
    _SetDeviceGammaRamp.argtypes = [wintypes.HDC, ctypes.c_void_p]

    _RampType = (ctypes.c_uint16 * 256) * 3

    def _with_primary_dc(fn):
        hdc = _GetDC(0)
        if not hdc:
            return None
        try:
            return fn(hdc)
        finally:
            _ReleaseDC(0, hdc)

    def capture_original() -> None:
        global _supported, _original
        ramp = _RampType()

        def _read(hdc):
            return bool(_GetDeviceGammaRamp(hdc, ctypes.byref(ramp)))

        ok = _with_primary_dc(_read)
        if ok:
            _original = ramp
            _supported = True
        else:
            _original = None
            _supported = False

    def apply(rgb_scale: tuple[float, float, float]) -> bool:
        if not _supported or _original is None:
            return False
        r_s, g_s, b_s = (max(0.0, min(1.0, s)) for s in rgb_scale)
        scales = (r_s, g_s, b_s)
        new_ramp = _RampType()
        for c in range(3):
            s = scales[c]
            for i in range(256):
                v = int(_original[c][i] * s)
                if v < 0:
                    v = 0
                elif v > 65535:
                    v = 65535
                new_ramp[c][i] = v

        def _write(hdc):
            return bool(_SetDeviceGammaRamp(hdc, ctypes.byref(new_ramp)))

        return bool(_with_primary_dc(_write))

    def restore() -> None:
        if not _supported or _original is None:
            return

        def _write(hdc):
            return bool(_SetDeviceGammaRamp(hdc, ctypes.byref(_original)))

        _with_primary_dc(_write)

else:
    # Non-Windows: no-op stubs so imports and tests still work.
    def capture_original() -> None:  # pragma: no cover
        global _supported
        _supported = False

    def apply(rgb_scale: tuple[float, float, float]) -> bool:  # pragma: no cover
        return False

    def restore() -> None:  # pragma: no cover
        return

    def set_app_user_model_id(app_id: str) -> None:  # pragma: no cover
        return


def is_supported() -> bool:
    return _supported
