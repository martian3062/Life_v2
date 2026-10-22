"""Read-only liveness checks for the game process owning a physics worker."""

import ctypes
import os

if os.name == "nt":
    from ctypes import wintypes

    _kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    _kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _kernel.OpenProcess.restype = wintypes.HANDLE
    _kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    _kernel.WaitForSingleObject.restype = wintypes.DWORD
    _kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel.CloseHandle.restype = wintypes.BOOL


def process_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        handle = _kernel.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE only
        if not handle:
            return ctypes.get_last_error() == 5  # Access denied is not proof of exit.
        try:
            return _kernel.WaitForSingleObject(handle, 0) == 258  # WAIT_TIMEOUT
        finally:
            _kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
