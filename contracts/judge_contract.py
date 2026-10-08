# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

"""
ContractJudge — on-chain GenLayer contract security auditor.

Accepts submitted Python contract code, runs it through gl.nondet.exec_prompt
for LLM analysis with validator consensus, and stores the verdict.
"""

import json
import re
from datetime import datetime, timezone
from dataclasses import dataclass
from genlayer import *


@allow_storage
@dataclass
class Submission:
    code: str = ""
    status: str = "pending"
    result: str = ""
    timestamp: u256 = u256(0)
    analyzer: str = ""
    resolved_at: u256 = u256(0)


# ---------------------------------------------------------------------------
# Module-level AI helpers (GenVM-safe: no @staticmethod, no local imports)
# ---------------------------------------------------------------------------

def _analyze_code(code: str) -> dict:
    """Run LLM security analysis on submitted contract code."""
    prompt = (
        "You are a GenLayer contract security auditor. Analyze the following "
        "Python GenLayer contract code for issues.\n\n"
        f"CONTRACT CODE:\n{code[:5000]}\n\n"
        "Check for:\n"
        "- Missing 'from genlayer import' statement\n"
        "- Missing @allow_storage or @gl.allow_storage decorator\n"
        "- Wrong decorator names (@public.read vs @gl.public.view, etc.)\n"
        "- Missing return type annotations on @gl.public.view methods\n"
        "- Bare except: clauses\n"
        "- Stub methods (only pass or ...)\n"
        "- Mutable default arguments\n"
        "- gl.nondet.exec_prompt called with unsanitized user input (prompt injection)\n"
        "- Collection types as storage dataclass fields (rejected by GenVM)\n"
        "- bigint assigned plain values instead of u256\n"
        "- @staticmethod or local imports (rejected by GenVM)\n\n"
        "Respond with ONLY a valid JSON object in this exact format:\n"
        '{"severity": "critical|high|medium|low|none", "issues": ["..."], "strengths": ["..."], "recommended": true|false}\n\n'
        "Rules:\n"
        "- severity: 'critical' if missing imports or missing @allow_storage; 'high' if bare except or wrong decorators; 'medium' for other issues; 'none' if clean\n"
        "- issues: list of specific problem descriptions\n"
        "- strengths: list of things done correctly\n"
        "- recommended: false if critical or high issues found\n"
        "- Do NOT include any text outside the JSON object"
    )
    raw = gl.nondet.exec_prompt(prompt).strip()
    return _parse_verdict_json(raw)


def _parse_verdict_json(raw: str) -> dict:
    """Defensively parse LLM JSON output."""
    raw = re.sub(r"```json\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"```\s*", "", raw)
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if match:
        raw = match.group()
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            severity = data.get("severity", "none")
            if severity not in ("critical", "high", "medium", "low", "none"):
                severity = "none"
            return {
                "severity": severity,
                "issues": data.get("issues", []),
                "strengths": data.get("strengths", []),
                "recommended": data.get("recommended", True),
            }
    except (json.JSONDecodeError, KeyError):
        pass
    raw_upper = raw.upper()
    for v in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "NONE"):
        if v in raw_upper:
            return {"severity": v.lower(), "issues": [raw[:200]], "strengths": [], "recommended": False}
    return {"severity": "none", "issues": ["Could not parse LLM output"], "strengths": [], "recommended": False}


# ---------------------------------------------------------------------------
# The contract
# ---------------------------------------------------------------------------

class ContractJudge(gl.Contract):
    """On-chain GenLayer contract security auditor with LLM consensus."""

    submissions: TreeMap[str, Submission]
    submission_count: u256 = u256(0)

    def __init__(self):
        self.submission_count = u256(0)

    def _now(self) -> int:
        return int(datetime.now(timezone.utc).timestamp())

    @gl.public.write
    def submit_contract(self, code: str) -> str:
        """Submit contract code for analysis. Returns submission ID."""
        if not code or not code.strip():
            raise gl.vm.UserError("Empty contract code submitted")
        sid = str(int(self.submission_count))
        self.submission_count += u256(1)
        self.submissions[sid] = Submission(
            code=code,
            status="pending",
            result="",
            timestamp=u256(self._now()),
        )
        return sid

    @gl.public.write
    def analyze(self, submission_id: str) -> str:
        """Run LLM analysis on a submitted contract. Validators consensus on the result."""
        submission_id = str(submission_id)
        sub = self.submissions.get(submission_id, None)
        if sub is None:
            raise gl.vm.UserError("Submission not found")
        if sub.status != "pending":
            raise gl.vm.UserError("Submission already analyzed")

        code = sub.code

        # ---- nondeterministic round (leader/validator) -------------------
        def leader_fn() -> dict:
            return _analyze_code(code)

        def validator_fn(leader_res) -> bool:
            if not isinstance(leader_res, gl.vm.Return):
                return False
            mine = _analyze_code(code)
            return mine.get("severity") == leader_res.calldata.get("severity")

        result = gl.vm.run_nondet(leader_fn, validator_fn)

        # run_nondet returns gl.vm.Return; access .calldata for the dict
        result_data = result.calldata if hasattr(result, "calldata") else result
        severity = result_data.get("severity", "none")
        issues = result_data.get("issues", [])
        strengths = result_data.get("strengths", [])
        recommended = result_data.get("recommended", True)

        if severity not in ("critical", "high", "medium", "low", "none"):
            severity = "none"

        verdict = {
            "submission_id": submission_id,
            "severity": severity,
            "issues": issues,
            "strengths": strengths,
            "recommended": recommended,
            "analyzed_at": self._now(),
            "analyzer": str(gl.message.sender_address),
        }

        sub.status = "analyzed"
        sub.result = json.dumps(verdict)
        sub.analyzer = str(gl.message.sender_address)
        sub.resolved_at = u256(self._now())
        self.submissions[submission_id] = sub

        return severity

    @gl.public.view
    def get_verdict(self, submission_id: str) -> dict:
        """Read the stored verdict and full submission record."""
        submission_id = str(submission_id)
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
            "analyzer": sub.analyzer,
            "resolved_at": sub.resolved_at,
        }

    @gl.public.view
    def list_submissions(self) -> list:
        """List all submission IDs and statuses."""
        result = []
        for sid in self.submissions.keys():
            s = self.submissions[sid]
            result.append({
                "submission_id": sid,
                "status": s.status,
                "timestamp": s.timestamp,
                "analyzer": s.analyzer,
            })
        return result

    @gl.public.view
    def get_stats(self) -> dict:
        """Usage statistics."""
        total = self.submission_count
        analyzed = sum(1 for s in self.submissions.values() if s.status == "analyzed")
        pending = sum(1 for s in self.submissions.values() if s.status == "pending")
        return {"total_submissions": total, "analyzed": analyzed, "pending": pending}
