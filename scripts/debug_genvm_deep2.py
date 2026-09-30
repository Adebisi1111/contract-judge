#!/usr/bin/env python3.14
"""
Deep GENVM bytecode simulation and comparison.
Compares the exact bytecode patterns that GENVM might reject.
"""

import json, re, os, struct, hashlib
from pathlib import Path
from dataclasses import dataclass, field, fields as dc_fields, is_dataclass

# Monkey-patch genlayer imports (these don't exist until GENVM runs them,
# but we can simulate what the bytecode would look like)

# Simulate what happens when genlayer-js compiles a Python contract
# The key insight: genlayer-js uses jiti to compile Python -> GENVM bytecode
# and the metadata.json must have "runner": "GenVM"

print("=" * 70)
print("GENVM BYTECODE SIMULATION & COMPARISON")
print("OracleNetwork (works) vs ContractJudge (fails)")
print("=" * 70)

# Read sources
oracle_src_path = "/home/administrator/oracle-network/contracts/oracle_network.py"
judge_src_path = "/home/administrator/contract-judge/contracts/judge_contract.py"

with open(oracle_src_path) as f:
    oracle_src = f.read()
with open(judge_src_path) as f:
    judge_src = f.read()

# 1. Check for Python features that might not translate to GENVM bytecode
print("\n--- Python feature compatibility ---")

features = {
    "Dataclass with @allow_storage": lambda s: "@allow_storage" in s and "@dataclass" in s,
    "TreeMap with custom dataclass as value type": lambda s: bool(re.search(r'TreeMap\[.*?,.*Record.*\]', s)),
    "TreeMap with Submission as value type": lambda s: "TreeMap[str, Submission]" in s,
    "DynArray storage": lambda s: "DynArray" in s,
    "gl.now() call": lambda s: "gl.now()" in s,
    "str(self.xxx) conversion": lambda s: bool(re.search(r'str\(self\.\w+\)', s)),
    "int(self.xxx) conversion": lambda s: bool(re.search(r'int\(self\.\w+\)', s)),
    "u256(self.xxx) conversion": lambda s: bool(re.search(r'u256\(self\.\w+\)', s)),
    "json.loads/dumps": lambda s: "json.loads" in s or "json.dumps" in s,
    "f-string in prompt": lambda s: bool(re.search(r'f".*?\{.*?\}.*?"', s)),
    "Generator expressions": lambda s: "for .* in .* if" in s and "sum(" in s,
    "Nested function closures": lambda s: bool(re.search(r'def \w+\(\):.*def \w+\(', s, re.DOTALL)),
    "Ternary operators": lambda s: "if .* else" in s,
    "List comprehensions": lambda s: bool(re.search(r'\[.* for .* in .* (if .*)?\]', s)),
    "Dict comprehensions": lambda s: bool(re.search(r'\{.*: .* for .* in .*\}', s)),
    "Try/except blocks": lambda s: "try:" in s and "except" in s,
    "Multiple except clauses": lambda s: bool(re.search(r'except.*:\s*.*\n\s*except', s, re.DOTALL)),
    "raise gl.vm.UserError": lambda s: "raise gl.vm.UserError" in s,
    "gl.message() calls": lambda s: "gl.message" in s,
}

print("\nFeature comparison (YES = present in source):")
differences = []
for feat_name, feat_fn in features.items():
    o = "YES" if feat_fn(oracle_src) else "no"
    j = "YES" if feat_fn(judge_src) else "no"
    diff = ""
    if o != j:
        diff = " <-- DIFFERS"
        differences.append((feat_name, o, j))
    print(f"  {feat_name}: oracle={o}, judge={j}{diff}")

print(f"\nTotal differences: {len(differences)}")
for name, o, j in differences:
    print(f"  - {name}: oracle={o}, judge={j}")

# 2. Simulate GENVM bytecode compilation (what genlayer-js likely does)
print("\n--- Simulated bytecode analysis ---")

# GENVM likely rejects:
# a) Unknown types in storage (e.g., custom class as TreeMap value without @allow_storage)
# b) Methods that reference undeclared names
# c) Non-deterministic imports (random, time, etc. - though datetime is used by oracle)
# d) Complex nested structures that can't be serialized

# Check for unknown type references
print("\nType reference analysis:")
def find_type_references(src):
    """Find all type references in storage declarations and method signatures."""
    types = set()
    # Storage field types
    for m in re.finditer(r'^\s+(\w+):\s+(\w+(?:\[.*?\])?)\s*(?:=\s*(.+?))?\s*$', src, re.MULTILINE):
        ftype = m.group(2)
        # Extract inner types from generics
        for tm in re.finditer(r'(\w+(?:\[.*?\])?)', ftype):
            types.add(tm.group(1))
    # Method param types
    for m in re.finditer(r'def\s+\w+\s*\(([^)]*)\)\s*->\s*([^\n:]+):', src):
        params = m.group(1)
        for pm in re.finditer(r'(\w+):\s*(\w+(?:\[.*?\])?)', params):
            types.add(pm.group(2))
    return types

oracle_types = find_type_references(oracle_src)
judge_types = find_type_references(judge_src)

print(f"  Oracle types: {sorted(oracle_types)}")
print(f"  Judge types:  {sorted(judge_types)}")

all_types = oracle_types | judge_types
for t in sorted(all_types):
    in_o = "YES" if t in oracle_types else "no"
    in_j = "YES" if t in judge_types else "no"
    diff = " <-- DIFFERS" if in_o != in_j else ""
    print(f"    {t}: oracle={in_o}, judge={in_j}{diff}")

# 3. Check TreeMap value type specifically
print("\n--- TreeMap value type analysis ---")
oracle_treemaps = re.findall(r'TreeMap\[(.*?),\s*(\w+)\]', oracle_src)
judge_treemaps = re.findall(r'TreeMap\[(.*?),\s*(\w+)\]', judge_src)

print("Oracle TreeMaps:")
for key_type, val_type in oracle_treemaps:
    o_decl = f"TreeMap[{key_type}, {val_type}]"
    print(f"  {o_decl}")
    # Check if value type is a custom class
    if val_type not in ('str', 'u256', 'bool', 'bytes', 'int', 'list', 'dict'):
        print(f"    -> Custom class value type: {val_type}")

print("Judge TreeMaps:")
for key_type, val_type in judge_treemaps:
    j_decl = f"TreeMap[{key_type}, {val_type}]"
    print(f"  {j_decl}")
    if val_type not in ('str', 'u256', 'bool', 'bytes', 'int', 'list', 'dict'):
        print(f"    -> Custom class value type: {val_type}")

# 4. Check the exact structure around class declaration  
print("\n--- Class declaration structure ---")

def get_class_structure(src):
    """Extract the class declaration block including decorators and first line."""
    m = re.search(r'(@[\w\.]+\s*\n)*class\s+\w+\s*\(\s*gl\.Contract\s*\)\s*:', src)
    if m:
        start = max(0, m.start() - 50)
        end = min(len(src), m.end() + 200)
        return src[start:end]
    return "NOT FOUND"

print("\nOracle class declaration:")
print(textwrap.indent(get_class_structure(oracle_src), "  "))

print("\nJudge class declaration:")
print(textwrap.indent(get_class_structure(judge_src), "  "))

# 5. Check what genlayer-js expects in metadata
print("\n--- genlayer-js metadata expectations ---")
print("genlayer-js (v1.1.8) compiles Python via jiti and expects:")
print("  - Metadata with 'runner': 'GenVM'")
print("  - Bytecode as hex string")
print("  - Source mapping")
print()
print("If the compiled bytecode has invalid opcodes or unsupported patterns,")
print("GENVM will reject with exit_code 1.")

# 6. Check if there's a version mismatch
print("\n--- Version compatibility ---")
genlayer_pkg_path = "/home/administrator/contract-judge/node_modules/genlayer-js/package.json"
if os.path.exists(genlayer_pkg_path):
    with open(genlayer_pkg_path) as f:
        pkg = json.load(f)
    print(f"genlayer-js version: {pkg.get('version', 'unknown')}")
    deps = pkg.get('dependencies', {})
    for dep_name, dep_ver in deps.items():
        print(f"  dependency: {dep_name}@{dep_ver}")

# 7. Check if submission_count default is the issue
print("\n--- Default value analysis ---")
print("Oracle: submission_count-like fields use = u256(0)")
print("Judge:  submission_count uses = u256(0)")
print("Both: TreeMap fields in Oracle have NO default, Judge had = TreeMap()")

# The key test: does Oracle's TreeMap without default work?
# Oracle: oracles: TreeMap[str, OracleRecord]  (no = TreeMap())
# Judge:  submissions: TreeMap[str, Submission] = TreeMap()  (has default)
print("\n>>> KEY DIFFERENCE: Oracle TreeMaps have NO default value")
print(">>> Judge TreeMaps had = TreeMap() default (now removed in latest)")
print(">>> This could cause GENVM to reject the contract during init")

# 8. Check the exact TreeMap default pattern
print("\n--- TreeMap storage declaration patterns ---")

oracle_treemap_lines = [l.strip() for l in oracle_src.split('\n') if 'TreeMap' in l and ':' in l and not l.strip().startswith('#')]
judge_treemap_lines = [l.strip() for l in judge_src.split('\n') if 'TreeMap' in l and ':' in l and not l.strip().startswith('#')]

print("Oracle TreeMap declarations:")
for l in oracle_treemap_lines:
    print(f"  {l}")

print("Judge TreeMap declarations:")
for l in judge_treemap_lines:
    print(f"  {l}")

# 9. Check Submission dataclass structure
print("\n--- Submission dataclass structure ---")
submission_match = re.search(r'@allow_storage\s*\n@dataclass\s*\nclass\s+Submission.*?^\n(?=\s*class|\s*$|\Z)', judge_src, re.MULTILINE | re.DOTALL)
if submission_match:
    print(textwrap.indent(submission_match.group(0), "  "))

# OracleRecord structure
oracle_record_match = re.search(r'@allow_storage\s*\n@dataclass\s*\nclass\s+OracleRecord.*?^\n(?=\s*@|\s*class|\s*$|\Z)', oracle_src, re.MULTILINE | re.DOTALL)
if oracle_record_match:
    print("\nOracleRecord dataclass:")
    print(textwrap.indent(oracle_record_match.group(0), "  "))

# 10. Check for __init__ body differences
print("\n--- __init__ body comparison ---")
oracle_init = re.search(r'def __init__\(self\):.*?(?=\n    @|\nclass |\Z)', oracle_src, re.DOTALL)
judge_init = re.search(r'def __init__\(self\):.*?(?=\n    @|\nclass |\Z)', judge_src, re.DOTALL)

if oracle_init:
    print("Oracle __init__:")
    print(textwrap.indent(oracle_init.group(0).strip(), "  "))
if judge_init:
    print("\nJudge __init__:")
    print(textwrap.indent(judge_init.group(0).strip(), "  "))

print("\n=== END ANALYSIS ===")
