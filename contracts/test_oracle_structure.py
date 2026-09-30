# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

"""
Minimal counter for GenLayer testing.
========================================
"""

import json
import math
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Any

from genlayer import *  # noqa: F401, F403


@allow_storage
@dataclass
class Record:
    value: u256 = u256(0)
    active: bool = True


@allow_storage
@dataclass
class Request:
    data: str = ""
    status: str = "PENDING"


class MinimalJudge(gl.Contract):
    """Minimal judge contract."""

    OUTLIER_THRESHOLD: u256 = u256(200)
    min_stake: u256 = u256(1000000000000000000)
    records: TreeMap[str, Record]
    requests: TreeMap[str, Request]

    def __init__(self):
        self.min_stake = u256(1000000000000000000)
        self.OUTLIER_THRESHOLD = u256(200)

    @gl.public.write
    def increment(self) -> u256:
        self.min_stake += u256(1)
        return self.min_stake

    @gl.public.read
    def get_count(self) -> u256:
        return self.min_stake
