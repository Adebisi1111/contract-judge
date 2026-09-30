# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

"""ContractJudge - GenLayer contract security auditor (matches OracleNetwork TreeMap pattern)."""

import json
from dataclasses import dataclass
from genlayer import *


@allow_storage
@dataclass
class Submission:
    code: str = ""
    status: str = "pending"
    result: str = ""
    timestamp: u256 = u256(0)


class ContractJudge(gl.Contract):
    submissions: TreeMap[str, Submission]
    submission_count: u256 = u256(0)

    def __init__(self):
        self.submission_count = u256(0)

    @gl.public.write
    def submit_contract(self, code: str) -> str:
        if not code or not code.strip():
            gl.message("Empty contract code submitted")
            return ""
        sid = str(self.submission_count)
        self.submission_count += 1
        self.submissions[sid] = Submission(
            code=code, status="pending", result="", timestamp=gl.now())
        return sid

    @gl.public.read
    def get_verdict(self, submission_id: str) -> dict:
        sub = self.submissions.get(submission_id, None)
        if sub is None:
            return {"error": "Not found", "exists": False}
        return {
            "exists": True,
            "submission_id": submission_id,
            "status": sub.status,
            "code_preview": sub.code[:500] if sub.code else "",
            "code_length": len(sub.code) if sub.code else 0,
            "result": json.loads(sub.result) if sub.result else None,
            "timestamp": sub.timestamp,
        }

    @gl.public.read
    def list_submissions(self) -> list:
        result = []
        for sid in self.submissions.keys():
            s = self.submissions[sid]
            result.append({"submission_id": sid, "status": s.status, "timestamp": s.timestamp})
        return result

    @gl.public.read
    def get_stats(self) -> dict:
        total = self.submission_count
        analyzed = sum(1 for s in self.submissions.values() if s.status == "analyzed")
        pending = sum(1 for s in self.submissions.values() if s.status == "pending")
        return {"total_submissions": total, "analyzed": analyzed, "pending": pending}
