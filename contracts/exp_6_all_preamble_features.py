# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

"""Minimal counter for GenLayer testing.
========================================
"""
import json
from genlayer import *


class MinimalJudge(gl.Contract):
    """Minimal judge contract."""
    OUTLIER_THRESHOLD: u256 = u256(200)
    count: u256 = u256(0)
    def __init__(self):
        self.count = u256(0)
    @gl.public.write
    def increment(self) -> u256:
        self.count += 1
        return self.count
    @gl.public.read
    def get_count(self) -> u256:
        return self.count
