# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

"""Minimal TreeMap[str, str]."""
from genlayer import *


class TreeMapTest(gl.Contract):
    data: TreeMap[str, str]
    count: u256 = u256(0)

    def __init__(self):
        self.count = u256(0)

    @gl.public.write
    def set(self, key: str, value: str) -> str:
        self.data[key] = value
        self.count += 1
        return value

    @gl.public.read
    def get(self, key: str) -> str:
        return self.data.get(key, "")
