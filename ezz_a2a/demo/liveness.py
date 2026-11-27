"""Check whether a process is running and end it, on Windows and POSIX."""

import os
import signal
import subprocess

from ezz_a2a.claude.process_tree import IS_WINDOWS

ZOMBIE_STATE_PREFIX = "Z"
STILL_ACTIVE = 259
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_TERMINATE = 0x0001
TERMINATED_EXIT_CODE = 1


def _load_kernel32():
    import ctypes
    from ctypes import wintypes
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.TerminateProcess.argtypes = (wintypes.HANDLE, wintypes.UINT)
    kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, wintypes.LPDWORD)
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    return kernel32


def _is_alive_windows(pid: int) -> bool:
    import ctypes
    from ctypes import wintypes
    kernel32 = _load_kernel32()
    process_handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not process_handle:
        return False
    try:
        exit_code = wintypes.DWORD()
        kernel32.GetExitCodeProcess(process_handle, ctypes.byref(exit_code))
        return exit_code.value == STILL_ACTIVE
    finally:
        kernel32.CloseHandle(process_handle)


def _is_alive_posix(pid: int) -> bool:
    state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)],
                           capture_output=True, text=True).stdout.strip()
    return bool(state) and not state.startswith(ZOMBIE_STATE_PREFIX)


def is_alive(pid: int) -> bool:
    return _is_alive_windows(pid) if IS_WINDOWS else _is_alive_posix(pid)


def terminate(pid: int) -> None:
    if not IS_WINDOWS:
        os.kill(pid, signal.SIGKILL)
        return
    kernel32 = _load_kernel32()
    process_handle = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
    if process_handle:
        kernel32.TerminateProcess(process_handle, TERMINATED_EXIT_CODE)
        kernel32.CloseHandle(process_handle)
