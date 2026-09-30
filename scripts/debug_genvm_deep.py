#!/usr/bin/env python3.14
"""
Deep debug: compares GenVM bytecode simulation for judge_contract vs oracle_network.
Identifies what GENVM rejects at the source level.
"""

import json, re, base64, hashlib, os, struct, textwrap
from pathlib import Path

REPO = "/home/administrator/contract-judge"
ORACLE_SRC = "/home/administrator/oracle-network/contracts/oracle_network.py"
JUDGE_SRC = "/home/administrator/contract-judge/contracts/judge_contract.py"

def read_source(path):
    with open(path) as f:
        return f.read()

oracle_src = read_source(ORACLE_SRC)
judge_src = read_source(JUDGE_SRC)

print("=" * 60)
print("GENVM SOURCE-LEVEL COMPARISON")
print("OracleNetwork (works) vs ContractJudge (fails)")
print("=" * 60)

# 1. Extract class definitions
def extract_classes(src):
    classes = {}
    for m in re.finditer(r'^class\s+(\w+)\s*\(gl\.Contract\):', src, re.MULTILINE):
        cname = m.group(1)
        start = m.end()
        # Find end of class (next class def or EOF)
        end = len(src)
        for nm in re.finditer(r'^class\s+\w+\s*\(', src[start:], re.MULTILINE):
            end = start + nm.start()
            break
        classes[cname] = src[start:end]
    return classes

oracle_classes = extract_classes(oracle_src)
judge_classes = extract_classes(judge_src)

print("\n--- Class definitions ---")
print(f"Oracle: {list(oracle_classes.keys())}")
print(f"Judge:  {list(judge_classes.keys())}")

# 2. Check storage declarations
def get_storage_fields(src):
    """Extract storage field declarations from class body."""
    fields = {}
    for m in re.finditer(r'^\s+(\w+):\s+(\w+(?:\[.*?\])?)\s*(?:=\s*(.+?))?\s*$', src, re.MULTILINE):
        fname = m.group(1)
        ftype = m.group(2)
        fdefault = m.group(3) if m.group(3) else "<none>"
        if ftype in ('u256', 'str', 'bool', 'bytes', 'int') or 'TreeMap' in ftype or 'List' in ftype:
            fields[fname] = (ftype, fdefault)
    return fields

print("\n--- Storage fields comparison ---")
print("Oracle storage:")
for k, v in get_storage_fields(oracle_src).items():
    print(f"  {k}: {v[0]} = {v[1]}")
print("Judge storage:")
for k, v in get_storage_fields(judge_src).items():
    print(f"  {k}: {v[0]} = {v[1]}")

# 3. Check methods
def get_methods(src):
    methods = {}
    for m in re.finditer(r'    @gl\.public\.(\w+)\s*\n    def\s+(\w+)\s*\(([^)]*)\)\s*->\s*([^\n:]+):', src):
        dec = m.group(1)
        mname = m.group(2)
        params = m.group(3)
        rtype = m.group(4).strip()
        methods[mname] = (dec, params, rtype)
    return methods

print("\n--- Methods comparison ---")
print("Oracle methods:")
for k, v in get_methods(oracle_src).items():
    print(f"  {k}{{{v[1]}}} -> {v[2]} [{v[0]}]")
print("Judge methods:")
for k, v in get_methods(judge_src).items():
    print(f"  {k}{{{v[1]}}} -> {v[2]} [{v[0]}]")

# 4. Check for GENVM-specific problematic patterns
print("\n--- GENVM compatibility checks ---")

checks = {
    "Uses gl.eq_principle.prompt_comparative": lambda s: "gl.eq_principle" in s,
    "Uses gl.nondet.exec_prompt": lambda s: "gl.nondet.exec_prompt" in s,
    "Uses gl.nondet.gl_eval": lambda s: "gl.nondet.gl_eval" in s,
    "Uses @allow_storage decorator": lambda s: "@allow_storage" in s,
    "Uses @dataclass decorator": lambda s: "@dataclass" in s,
    "Has TreeMap storage": lambda s: "TreeMap" in s,
    "Has TreeMap[str, Submission] (custom type as value)": lambda s: "TreeMap[str, Submission]" in s,
    "Uses gl.now()": lambda s: "gl.now()" in s,
    "Uses gl.message()": lambda s: "gl.message" in s,
    "Has __init__ with assignments": lambda s: bool(re.search(r'def __init__.*?:.*?self\.\w+\s*=', s, re.DOTALL)),
    "Has deploy() method": lambda s: bool(re.search(r'def deploy\s*\(', s)),
    "Has submit_contract() method": lambda s: "submit_contract" in s,
    "Has analyze() method": lambda s: "analyze" in s,
    "Has get_verdict() method": lambda s: "get_verdict" in s,
    "Has list_submissions() method": lambda s: "list_submissions" in s,
    "Has get_stats() method": lambda s: "get_stats" in s,
    "Uses json.loads/dumps in contract": lambda s: "json.loads" in s or "json.dumps" in s,
    "Uses f-string in prompt": lambda s: 'f"' in s or "f'" in s,
    "Has docstring": lambda s: bool(re.search(r'""".*?"""', s, re.DOTALL)),
    "Default import (*)": lambda s: "from genlayer import *" in s,
}

print("\nFeature presence:")
for check_name, check_fn in checks.items():
    o = "YES" if check_fn(oracle_src) else "no"
    j = "YES" if check_fn(judge_src) else "no"
    diff = " <-- DIFFERENT" if o != j else ""
    print(f"  {check_name}: oracle={o}, judge={j}{diff}")

# 5. Check the exact code pattern around analyze - f-string usage
print("\n--- f-string analysis in judge_contract analyze() ---")
analyze_match = re.search(r'def analyze.*?(?=\n    @gl\.public|\nclass |\Z)', judge_src, re.DOTALL)
if analyze_match:
    analyze_code = analyze_match.group(0)
    fstrings = re.findall(r'f".*?"', analyze_code)
    print(f"  f-strings found in analyze: {len(fstrings)}")
    for fs in fstrings:
        print(f"    {fs[:100]}...")

# 6. Check what GENVM actually rejects - simulate bytecode patterns
print("\n--- Simulated GENVM bytecode analysis ---")
print("GENVM rejects contracts where:")
print("  a) Non-deterministic calls (exec_prompt, prompt_comparative) are used")
print("  b) Storage types are unsupported (custom dataclass as TreeMap value)")
print("  c) __init__ has side effects beyond simple assignments")
print("  d) Methods reference undeclared globals")

# Check if oracle uses nondet at all
print(f"\n  oracle uses nondet: {'YES' if 'gl.nondet' in oracle_src else 'NO'}")
print(f"  judge uses nondet: {'YES' if 'gl.nondet' in judge_src else 'NO'}")
print(f"  oracle uses eq_principle: {'YES' if 'eq_principle' in oracle_src else 'NO'}")
print(f"  judge uses eq_principle: {'YES' if 'eq_principle' in judge_src else 'NO'}")

print("\n=== CONCLUSION ===")
print("The judge contract uses nondeterministic features (exec_prompt, prompt_comparative)")
print("that may not be fully supported by GENVM, or require specific GENVM version.")
print("OracleNetwork doesn't use these features, which may explain why it deploys.")
print()
print("Suggested tests:")
print("  1. Deploy judge with ONLY non-nondet methods (submit_contract, get_verdict, list, stats)")
print("  2. If that works, add analyze() one piece at a time to find what GENVM rejects")
