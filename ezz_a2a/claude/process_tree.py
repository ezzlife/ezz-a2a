"""Pick the process containment of the current operating system."""

import os

IS_WINDOWS = os.name == "nt"
# On Windows the process starts suspended: it cannot run, and so cannot start a
# child outside the job, until contain_process_tree has assigned it and resumed it.
CREATE_SUSPENDED = 0x00000004
SPAWN_OPTIONS = {"creationflags": CREATE_SUSPENDED} if IS_WINDOWS else {"start_new_session": True}


def contain_process_tree(pid: int):
    """Return an object with terminate() and close() for the tree rooted at pid."""
    if IS_WINDOWS:
        from ezz_a2a.claude.windows_job import contain_with_job_object
        return contain_with_job_object(pid)
    from ezz_a2a.claude.process_group import contain_process_group
    return contain_process_group(pid)
