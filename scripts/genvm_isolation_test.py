#!/usr/bin/env python3.14
"""Generate test contracts for GENVM isolation testing."""

import os

REPO = "/home/administrator/contract-judge"

# Test A: Exact OracleNetwork structure, minimal body
test_a = '''# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

"""
Minimal counter for GenLayer testing.
========================================
A simple counter contract for testing GENVM deployment.
"""

import json
from dataclasses import dataclass
from genlayer import *  # noqa: F401, F403


@allow_storage
@dataclass
class CounterRecord:
    value: u256 = u256(0)


class MinimalJudge(gl.Contract):
    """Minimal counter judge contract."""

    records: TreeMap[str, CounterRecord]
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
'''

# Test B: Same as A but WITHOUT the noqa comment
test_b = '''# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

"""
Minimal counter for GenLayer testing.
========================================
A simple counter contract for testing GENVM deployment.
"""

import json
from dataclasses import dataclass
from genlayer import *


@allow_storage
@dataclass
class CounterRecord:
    value: u256 = u256(0)


class MinimalJudge(gl.Contract):
    """Minimal counter judge contract."""

    records: TreeMap[str, CounterRecord]
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
'''

# Test C: Same as A but WITHOUT dataclass (just TreeMap[str, u256])
test_c = '''# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

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
'''

# Test D: OracleNetwork EXACT copy (should already work)
# test_oracle.py exists already

tests = [
    ("test_a_noqa.py", test_a, "OracleNetwork structure + noqa comment + dataclass"),
    ("test_b_nonoqa.py", test_b, "OracleNetwork structure - noqa comment + dataclass"),
    ("test_c_notreemap_custom.py", test_c, "OracleNetwork structure + noqa + NO dataclass (TreeMap[u256])"),
]

for filename, source, desc in tests:
    path = os.path.join(REPO, "contracts", filename)
    with open(path, "w") as f:
        f.write(source)
    print(f"Written {filename}: {desc}")
    print(f"  First line: {source.split(chr(10))[0]}")
    print(f"  Has noqa: {'# noqa' in source}")
    print(f"  Has dataclass: {'@dataclass' in source}")
    print(f"  Has TreeMap custom value: {'TreeMap[str,' in source and 'Record' in source or 'Submission' in source}")
    print()
