"""Show why the Claude worker contains its whole process tree.

Starts a three-level process tree (a stand-in for claude -> node -> tool),
simulates a timeout and counts the processes still alive. Run once with a plain
kill and once with the containment that the Claude runner uses (a Job Object on
Windows, a process group on Linux and macOS). No Claude call, no quota.
"""

import argparse
import os
import subprocess
import sys
import threading
import time

from ezz_a2a.claude.process_tree import SPAWN_OPTIONS, contain_process_tree
from ezz_a2a.demo.liveness import is_alive, terminate
from ezz_a2a.settings import EXIT_FAILURE, EXIT_SUCCESS

ROOT_LEVEL = 1
TREE_DEPTH = 3
CHILD_SPAWN_DELAY_SECONDS = 0.5  # The parent must be contained before it spawns its child.
LEVEL_LIFETIME_SECONDS = 120
TREE_READY_TIMEOUT_SECONDS = 10
SETTLE_SECONDS = 1.0
LEVEL_COMMAND = [sys.executable, "-m", "ezz_a2a.demo", "--level"]


def run_level(level: int) -> None:
    """One process of the tree: print its PID on the shared stdout, then spawn the next level."""
    print(os.getpid(), flush=True)
    if level < TREE_DEPTH:
        time.sleep(CHILD_SPAWN_DELAY_SECONDS)
        subprocess.Popen([*LEVEL_COMMAND, str(level + 1)], stdout=sys.stdout)
    time.sleep(LEVEL_LIFETIME_SECONDS)


def read_level_pids(root_process) -> list[int]:
    """Read one PID per level from the root's stdout; a watchdog bounds the wait."""
    watchdog = threading.Timer(TREE_READY_TIMEOUT_SECONDS, root_process.kill)
    watchdog.start()
    try:
        return [int(root_process.stdout.readline()) for _ in range(TREE_DEPTH)]
    except ValueError:
        raise TimeoutError("The process tree did not start in time") from None
    finally:
        watchdog.cancel()


def count_survivors_of_timeout(contained: bool) -> int:
    """Simulate a timeout and return how many processes of the tree outlive it."""
    # SPAWN_OPTIONS start the process suspended on Windows until it is contained,
    # so the uncontained run starts it normally.
    spawn_options = SPAWN_OPTIONS if contained else {}
    root_process = subprocess.Popen([*LEVEL_COMMAND, str(ROOT_LEVEL)], stdout=subprocess.PIPE,
                                    text=True, **spawn_options)
    process_tree = contain_process_tree(root_process.pid) if contained else None
    level_pids = read_level_pids(root_process)
    if process_tree:
        process_tree.terminate()
        process_tree.close()
    else:
        root_process.kill()
    root_process.wait()
    time.sleep(SETTLE_SECONDS)
    survivors = [pid for pid in level_pids if is_alive(pid)]
    for pid in survivors:
        terminate(pid)
    root_process.stdout.close()
    return len(survivors)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--level", type=int, choices=range(ROOT_LEVEL, TREE_DEPTH + 1),
                        help=argparse.SUPPRESS)
    arguments = parser.parse_args()
    if arguments.level:
        run_level(arguments.level)
        return EXIT_SUCCESS
    print(f"Process tree of {TREE_DEPTH} levels, simulated timeout after it is up.\n")
    plain_kill_survivors = count_survivors_of_timeout(contained=False)
    print(f"Plain kill of the root : {plain_kill_survivors} of {TREE_DEPTH} processes still running")
    contained_survivors = count_survivors_of_timeout(contained=True)
    print(f"Contained terminate    : {contained_survivors} of {TREE_DEPTH} processes still running")
    demonstrated = plain_kill_survivors > 0 and contained_survivors == 0
    return EXIT_SUCCESS if demonstrated else EXIT_FAILURE
