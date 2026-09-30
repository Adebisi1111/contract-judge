# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

"""Minimal TreeMap[str, Submission]."""
import json
from dataclasses import dataclass
from genlayer import *


@allow_storage
@dataclass
class Submission:
    code: str = ""
    status: str = "pending"


class SubmissionJudge(gl.Contract):
    submissions: TreeMap[str, Submission]
    count: u256 = u256(0)

    def __init__(self):
        self.count = u256(0)

    @gl.public.write
    def submit(self, code: str) -> str:
        sid = str(self.count)
        self.count += 1
        self.submissions[sid] = Submission(code=code, status="pending")
        return sid

    @gl.public.read
    def get(self, sid: str) -> str:
        sub = self.submissions.get(sid, None)
        if sub is None:
            return ""
        return sub.code
