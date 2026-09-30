# { "Depends": "py-genlayer:4e4395a1552ff71a5b928c14f823aec4083111a2e79bb1b7d23b2ef9d4b1d91c" }

"""Test."""
from genlayer import *


class MinimalJudge(gl.Contract):
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
