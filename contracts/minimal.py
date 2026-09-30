# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

from genlayer import *


class Minimal(gl.Contract):
    count: u256 = u256(0)

    def __init__(self):
        self.count = u256(0)

    @gl.public.write
    def inc(self) -> u256:
        self.count += 1
        return self.count

    @gl.public.view
    def get_count(self) -> u256:
        return self.count
