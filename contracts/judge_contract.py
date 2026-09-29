"""
ContractJudge — GenLayer Intelligent Contract

Accepts submitted Python contract code, runs LLM-based security analysis
via gl.nondet.exec_prompt, and stores the verdict. Validators reach
consensus on the LLM output — the "validator as judge" pattern.

Usage:
    judge = ContractJudge()
    judge.deploy()

    # User submits a contract for judging
    submission_id = judge.submit_contract(contract_code)

    # LLM analysis runs (validators consensus)
    result = judge.analyze(submission_id)

    # Read the verdict
    verdict = judge.get_verdict(submission_id)
"""

from genlayer import *
import json


@allow_storage
class ContractJudge:
    """Judge contract — LLM-powered contract security auditor."""

    # Storage
    submissions: TreeMap[str, dict] = TreeMap()
    """submission_id → {code, status, result, timestamp}"""

    submission_count: int = 0
    """Number of submissions received."""

    # Analysis prompt — sent to LLM for each submission
    _ANALYSIS_PROMPT = """
You are an expert blockchain smart contract security auditor. Analyze the following
Python contract code written for the GenLayer blockchain (using the genlayer SDK).

Identify ALL issues, bugs, security vulnerabilities, and deviations from best practices.
Be specific and actionable — cite line numbers where possible.

Contract code to analyze:

```python
{code}
```

Return a JSON object with this exact structure. Do NOT include any text outside the JSON:

{
  "verdict": "pass" | "fail",
  "issues": [
    {
      "severity": "critical" | "high" | "medium" | "low",
      "title": "short title",
      "description": "detailed explanation",
      "line": <line_number or null>
    }
  ],
  "summary": "brief 1-2 sentence summary of findings"
}

Rules:
- verdict = "fail" if ANY critical or high severity issue exists, otherwise "pass"
- Be honest — if the contract looks clean, report fewer issues with low severity
- Focus on: missing imports, wrong decorators, storage issues, reentrancy, error handling,
  type safety, logic bugs, non-determinism risks, prompt injection risks
- Do NOT flag stylistic preferences unless they affect correctness
"""

    @public.write.payable
    def deploy(self) -> None:
        """Deploy the judge contract. Called once."""
        pass

    @public.write
    def submit_contract(self, code: str) -> str:
        """Submit a contract for LLM-powered security analysis.

        Args:
            code: Full Python source code of the contract to judge.

        Returns:
            Unique submission ID (string) that can be used to retrieve the verdict.
        """
        if not code or not code.strip():
            gl.message("Empty contract code submitted")
            return ""

        submission_id = str(self.submission_count)
        self.submission_count += 1

        # Store submission as pending
        self.submissions[submission_id] = {
            "code": code,
            "status": "pending",
            "result": None,
            "timestamp": gl.now(),
        }

        return submission_id

    @public.write
    def analyze(self, submission_id: str) -> dict:
        """Run LLM security analysis on a submitted contract.

        Validators reach consensus on the LLM's output via the equivalence
        principle. If validators disagree, the leader rotates until consensus
        is reached.

        Args:
            submission_id: The submission ID returned by submit_contract.

        Returns:
            Analysis result dict with verdict, issues, and summary.
            Returns error dict if submission not found.
        """
        submission = self.submissions.get(submission_id, None)
        if submission is None:
            return {
                "error": f"Submission '{submission_id}' not found",
                "verdict": "error",
                "issues": [],
            }

        if submission["status"] == "analyzed":
            # Already analyzed — return cached result
            return submission["result"]

        # Build the prompt with the contract code
        prompt = self._ANALYSIS_PROMPT.format(code=submission["code"])

        # Call LLM via non-deterministic execution — validators consensus
        raw_result = gl.nondet.exec_prompt(prompt)

        # Parse the JSON response
        try:
            analysis = json.loads(raw_result)
        except (json.JSONDecodeError, Exception):
            analysis = {
                "verdict": "fail",
                "issues": [
                    {
                        "severity": "medium",
                        "title": "LLM returned unparseable response",
                        "description": f"The LLM analysis could not be parsed. Raw response: {raw_result[:500]}",
                        "line": None,
                    }
                ],
                "summary": "LLM analysis failed to produce valid JSON",
            }

        # Validate the structure
        if "verdict" not in analysis:
            analysis["verdict"] = "fail"
        if "issues" not in analysis:
            analysis["issues"] = []
        if "summary" not in analysis:
            analysis["summary"] = "No summary provided"

        # Normalize issues to expected format
        normalized_issues = []
        for issue in analysis.get("issues", []):
            normalized_issues.append({
                "severity": issue.get("severity", "medium"),
                "title": issue.get("title", "Unnamed issue"),
                "description": issue.get("description", ""),
                "line": issue.get("line", None),
            })
        analysis["issues"] = normalized_issues

        # Store result
        submission["status"] = "analyzed"
        submission["result"] = analysis
        self.submissions[submission_id] = submission

        return analysis

    @public.read
    def get_verdict(self, submission_id: str) -> dict:
        """Get the analysis verdict for a submission.

        Args:
            submission_id: The submission ID.

        Returns:
            Full submission record including code, status, and result.
            Returns error dict if not found.
        """
        submission = self.submissions.get(submission_id, None)
        if submission is None:
            return {
                "error": f"Submission '{submission_id}' not found",
                "exists": False,
            }
        return {
            "exists": True,
            "submission_id": submission_id,
            "status": submission["status"],
            "code_preview": submission["code"][:500] if submission.get("code") else "",
            "code_length": len(submission.get("code", "")),
            "result": submission.get("result"),
            "timestamp": submission.get("timestamp"),
        }

    @public.read
    def list_submissions(self) -> list:
        """List all submission IDs and their status.

        Returns:
            List of {submission_id, status, timestamp} dicts.
        """
        result = []
        for sub_id in self.submissions.keys():
            sub = self.submissions[sub_id]
            result.append({
                "submission_id": sub_id,
                "status": sub["status"],
                "timestamp": sub.get("timestamp"),
            })
        return result

    @public.read
    def get_stats(self) -> dict:
        """Get contract usage statistics.

        Returns:
            Dict with total submissions, analyzed count, pending count.
        """
        total = self.submission_count
        analyzed = 0
        pending = 0
        for sub_id in self.submissions.keys():
            status = self.submissions[sub_id]["status"]
            if status == "analyzed":
                analyzed += 1
            elif status == "pending":
                pending += 1
        return {
            "total_submissions": total,
            "analyzed": analyzed,
            "pending": pending,
        }
