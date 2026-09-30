# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

"""
TestClone — Decentralized Oracle Consensus via GenLayer AI
=============================================================

A standalone GenLayer Intelligent Contract primitive for decentralized
data feeds. Multiple oracles report values for a data request; a single
AI consensus round determines the truthful value and slashes outliers.

PURPOSE
    Oracles stake GEN to participate. Requesters post data requests.
    Oracles use AI to fetch and evaluate data sources, then report a
    value. A single non-deterministic round identifies outliers and
    slashes them, producing a consensus value.

CONSENSUS
    Single gl.vm.run_nondet_unsafe call:
    1. leader_fn: compute median of all reports, identify outliers
       (values beyond 2σ from median), slash outlier oracles.
    2. validator_fn: recompute median independently, agree on which
       oracles to slash. Any mismatch → disagree → leader rotates.

STATE
    oracles    TreeMap[str, OracleRecord]   — stake, reports, slashes
    requests   TreeMap[str, Request]       — data request, status, result
    reports    TreeMap[str, Report]        — individual oracle reports

DEPLOY-TIME PARAMETERS
    min_stake_wei      — minimum stake to register (default 1 GEN)
    slash_percent      — fraction of stake burned on outlier (default 10%)
    outlier_threshold  — standard deviations for outlier detection (default 2.0)
"""

import json
import math
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Any

from genlayer import *  # noqa: F401, F403


@allow_storage
@dataclass
class OracleRecord:
    staked: u256 = u256(0)
    reports_count: u256 = u256(0)
    slashed_count: u256 = u256(0)
    total_slashed: u256 = u256(0)
    active: bool = True


@allow_storage
@dataclass
class Report:
    oracle: str = ""
    request_id: str = ""
    value: u256 = u256(0)
    source: str = ""
    timestamp: u256 = u256(0)


@allow_storage
@dataclass
class Request:
    requester: str = ""
    query: str = ""
    sources: DynArray[str] = field(default_factory=lambda: DynArray[str]())
    status: str = "PENDING"  # PENDING | RESOLVED | CANCELLED
    result: u256 = u256(0)
    reports_count: u256 = u256(0)
    resolved_at: u256 = u256(0)


class TestClone(gl.Contract):
    """Minimal judge contract."""
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
