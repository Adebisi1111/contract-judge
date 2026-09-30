# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

"""
Minimal counter for GenLayer testing.
========================================
"""

import json
from genlayer import *  # noqa: F401, F403


class MinimalJudge(gl.Contract):
    """Minimal counter judge contract."""

    data: TreeMap[str, u256]
    count: u256 = u256(0)

    def __init__(self):
        self.count = u256(0)

    @gl.public.write
    def set(self, key: str, value: u256) -> u256:
        self.data[key] = value
        self.count += 1
        return value

    @gl.public.read
    def get(self, key: str) -> u256:
        return self.data.get(key, u256(0))
