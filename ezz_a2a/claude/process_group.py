"""Contain a process and its descendants in a POSIX process group.

The process must have been started with start_new_session=True, which makes it
the leader of a group that its descendants inherit. Killing the group ends the
whole group on terminate() and on close(). The group exists from startup, but
descendants can escape it by creating a new session or process group.
"""

import os
import signal
import subprocess

from ezz_a2a.claude.errors import ProcessTreeError

PROCESS_INSPECTION_TIMEOUT_SECONDS = 5


def _only_zombies(group_id: int) -> bool:
    """Verify macOS's zombie-only EPERM case without hiding live survivors."""
    try:
        listing = subprocess.run(
            ["ps", "-axo", "pgid=,stat="], capture_output=True, text=True,
            check=True, timeout=PROCESS_INSPECTION_TIMEOUT_SECONDS,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    states = [fields[1] for line in listing.splitlines()
              if len(fields := line.split()) == 2 and fields[0] == str(group_id)]
    return bool(states) and all(state.startswith("Z") for state in states)


class _ProcessGroupTree:
    def __init__(self, group_id: int):
        self._group_id = group_id

    def terminate(self) -> None:
        self._kill_group()

    def close(self) -> None:
        self._kill_group()

    def _kill_group(self) -> None:
        try:
            os.killpg(self._group_id, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except PermissionError as error:
            if not _only_zombies(self._group_id):
                raise ProcessTreeError(error.errno, "Could not end process group") from error


def contain_process_group(pid: int) -> _ProcessGroupTree:
    try:
        group_id = os.getpgid(pid)
    except OSError as error:
        raise ProcessTreeError(error.errno, "getpgid failed") from error
    if group_id != pid:
        raise ProcessTreeError(0, "process is not the leader of its own group")
    return _ProcessGroupTree(group_id)
