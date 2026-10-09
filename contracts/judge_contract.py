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
    """Run LLM security analysis on submitted contract code.

    Kept deliberately small: the leader's nondet round must complete inside the
    block execution window, so the prompt is terse and the input is capped.
    """
    prompt = (
        "Audit this GenLayer Python contract. Reply with ONLY a JSON object.\n"
        f"CODE:\n{code[:2000]}\n\n"
        'Format: {"severity":"critical|high|medium|low|none","issues":[".."],'
        '"strengths":[".."],"recommended":true|false}\n'
        "critical=missing 'from genlayer import' or @allow_storage; "
        "high=bare except / @staticmethod / local import; none=clean. "
        "recommended=false if critical or high."
    )
    # exec_prompt with response_format="json" returns a parsed dict, not a
    # string — do not call string methods on it.
    res = gl.nondet.exec_prompt(prompt, response_format="json")
    if isinstance(res, str):
        res = _parse_verdict_json(res)
    if not isinstance(res, dict):
        res = {"severity": "none", "issues": ["analysis unavailable"], "strengths": [], "recommended": False}
    return {
        "severity": res.get("severity", "none"),
        "issues": _as_str_list(res.get("issues", [])),
        "strengths": _as_str_list(res.get("strengths", [])),
        "recommended": bool(res.get("recommended", True)),
    }


def _as_str_list(value) -> list:
    """Normalize a field that may be a list, a single string, or absent into a
    list of non-empty strings. Guards against the model returning issues as a
    bare string, which otherwise gets stored as one unparsed blob."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, (list, tuple)):
        out = []
        for item in value:
            if isinstance(item, str) and item.strip():
                out.append(item)
            elif item is not None:
                out.append(str(item))
        return out
    return [str(value)]


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
                "issues": _as_str_list(data.get("issues", [])),
                "strengths": _as_str_list(data.get("strengths", [])),
                "recommended": bool(data.get("recommended", True)),
            }
    except (json.JSONDecodeError, KeyError, ValueError):
        pass
    # The model sometimes wraps the JSON object inside a string field, or returns
    # the object nested under a single key. Try one more extraction pass.
    nested = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if nested and nested.group() != raw:
        try:
            data = json.loads(nested.group())
            if isinstance(data, dict) and "severity" in data:
                severity = data.get("severity", "none")
                if severity not in ("critical", "high", "medium", "low", "none"):
                    severity = "none"
                return {
                    "severity": severity,
                    "issues": _as_str_list(data.get("issues", [])),
                    "strengths": _as_str_list(data.get("strengths", [])),
                    "recommended": bool(data.get("recommended", True)),
                }
        except (json.JSONDecodeError, KeyError, ValueError):
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

        # ---- nondeterministic round ----------------------------------------
        # Uses gl.eq_principle.prompt_comparative, the primitive that reaches
        # consensus reliably on Bradbury (the synchronous run_nondet +
        # exec_prompt combination consistently hit LEADER_TIMEOUT here).
        # prompt_comparative: the leader produces the analysis; validators
        # judge whether it is an equivalent verdict. The comparison principle
        # is about the coarse verdict bucket, so two runs that agree the
        # contract is "blocking" vs "ok" reach consensus even if they pick
        # different exact labels — exact-label matching forked the round.
        def leader_fn() -> dict:
            return _analyze_code(code)

        principle = (
            "Two analyses are equivalent if they place the contract in the same "
            "verdict bucket: 'blocking' (severity critical or high) or 'ok' "
            "(medium, low, or none). They may differ on exact wording or on "
            "critical-vs-high and still agree. Disagree only if one says the "
            "contract is blocking and the other says it is fine."
        )

        result_data = gl.eq_principle.prompt_comparative(leader_fn, principle)
        if not isinstance(result_data, dict):
            result_data = {"severity": "none", "issues": ["analysis unavailable"], "strengths": [], "recommended": False}

        severity = result_data.get("severity", "none")
        if severity not in ("critical", "high", "medium", "low", "none"):
            severity = "none"
        issues = _as_str_list(result_data.get("issues", []))
        strengths = _as_str_list(result_data.get("strengths", []))
        recommended = bool(result_data.get("recommended", True))

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
