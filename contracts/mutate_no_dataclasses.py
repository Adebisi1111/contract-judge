# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

"""
Minimal.
"""
from genlayer import *


    @gl.public.write
    def increment(self) -> u256:
        self.min_stake += u256(1)
        return self.min_stake

    @gl.public.read
    def get_count(self) -> u256:
        return self.min_stake
