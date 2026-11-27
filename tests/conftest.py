"""Synthetic processes have no real PID: record Job Object use instead of calling Windows."""

import pytest

from ezz_a2a.claude import runner as claude_runner


class RecordingTree:
    def __init__(self, pid):
        self.pid = pid
        self.events = []

    def terminate(self):
        self.events.append("terminate")

    def close(self):
        self.events.append("close")


@pytest.fixture(autouse=True)
def process_trees(monkeypatch):
    trees = []

    def contain(pid):
        tree = RecordingTree(pid)
        trees.append(tree)
        return tree

    monkeypatch.setattr(claude_runner, "contain_process_tree", contain)
    return trees
