"""Contain a process and all its descendants in a Windows Job Object.

Killing claude.exe alone leaves its descendants alive. A job with
KILL_ON_JOB_CLOSE ends the whole tree on terminate(), on close() and, because
the handle belongs to this process, also when the server itself dies.
The runner starts the process suspended (process_tree.SPAWN_OPTIONS), so it is
in the job before it runs a single instruction; descendants inherit the job.
Resuming uses NtResumeProcess because asyncio exposes no thread handle. On a
process that is not suspended it is a no-op.
"""

import ctypes
from ctypes import wintypes

from ezz_a2a.claude.errors import ProcessTreeError

JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS = 9
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
PROCESS_TERMINATE = 0x0001
PROCESS_SET_QUOTA = 0x0100
PROCESS_SUSPEND_RESUME = 0x0800
STATUS_SUCCESS = 0
TERMINATED_EXIT_CODE = 1


class _BasicLimits(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _IoCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in (
        "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]


class _ExtendedLimits(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _BasicLimits), ("IoInfo", _IoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class _JobProcessTree:
    def __init__(self, kernel32, job_handle):
        self._kernel32 = kernel32
        self._job_handle = job_handle

    def terminate(self) -> None:
        if self._job_handle:
            self._kernel32.TerminateJobObject(self._job_handle, TERMINATED_EXIT_CODE)

    def close(self) -> None:
        """Closing the last handle kills every process still in the job."""
        if self._job_handle:
            self._kernel32.CloseHandle(self._job_handle)
            self._job_handle = None


def _load_kernel32():
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.CreateJobObjectW.argtypes = (wintypes.LPVOID, wintypes.LPCWSTR)
    kernel32.SetInformationJobObject.argtypes = (
        wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    kernel32.TerminateJobObject.argtypes = (wintypes.HANDLE, wintypes.UINT)
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    return kernel32


def _load_ntdll():
    ntdll = ctypes.WinDLL("ntdll")
    ntdll.NtResumeProcess.restype = ctypes.c_long
    ntdll.NtResumeProcess.argtypes = (wintypes.HANDLE,)
    return ntdll


def _fail(step: str) -> ProcessTreeError:
    return ProcessTreeError(ctypes.get_last_error(), f"{step} failed")


def _enable_kill_on_close(kernel32, job_handle) -> None:
    limits = _ExtendedLimits()
    limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not kernel32.SetInformationJobObject(
            job_handle, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
            ctypes.byref(limits), ctypes.sizeof(limits)):
        raise _fail("SetInformationJobObject")


def _assign_and_resume(kernel32, job_handle, pid: int) -> None:
    access = PROCESS_SET_QUOTA | PROCESS_TERMINATE | PROCESS_SUSPEND_RESUME
    process_handle = kernel32.OpenProcess(access, False, pid)
    if not process_handle:
        raise _fail("OpenProcess")
    try:
        if not kernel32.AssignProcessToJobObject(job_handle, process_handle):
            raise _fail("AssignProcessToJobObject")
        status = _load_ntdll().NtResumeProcess(process_handle)
        if status != STATUS_SUCCESS:
            raise ProcessTreeError(status, "NtResumeProcess failed")
    finally:
        kernel32.CloseHandle(process_handle)


def contain_with_job_object(pid: int) -> _JobProcessTree:
    kernel32 = _load_kernel32()
    job_handle = kernel32.CreateJobObjectW(None, None)
    if not job_handle:
        raise _fail("CreateJobObject")
    process_tree = _JobProcessTree(kernel32, job_handle)
    try:
        _enable_kill_on_close(kernel32, job_handle)
        _assign_and_resume(kernel32, job_handle, pid)
    except ProcessTreeError:
        process_tree.close()
        raise
    return process_tree
