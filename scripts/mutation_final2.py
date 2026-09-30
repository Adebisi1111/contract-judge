#!/usr/bin/env python3.14
"""Final mutation test with proper password handling and GENVM result checking."""

import subprocess, json, re, os, urllib.request, base64

REPO = "/home/administrator/contract-judge"
CLI = "/home/administrator/.local/bin/genlayer"
RPC = "https://studio.genlayer.com/api"

def run_deploy(source, name, timeout=200):
    path = os.path.join(REPO, "contracts", name)
    with open(path, "w") as f:
        f.write(source)
    cmd = f'echo "test1234" | "{CLI}" deploy --contract "{path}" --rpc {RPC} 2>&1'
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout,
                       cwd=REPO, env=dict(os.environ, HOME=os.path.expanduser("~")))
    return p.stdout

def parse_output(out):
    tx_m = re.search(r'(0x[a-fA-F0-9]{64})', out)
    addr_m = re.search(r"Contract Address':\s*'(0x[a-fA-F0-9]{40})'", out)
    success_m = re.search(r"execution_result:\s*'(SUCCESS|ERROR)'", out)
    results = re.findall(r"execution_result:\s*'([^']+)'", out)
    return {
        "tx": tx_m.group(1) if tx_m else None,
        "addr": addr_m.group(1) if addr_m else None,
        "last_exec": results[-1] if results else "?",
        "all_exec": results,
        "output": out
    }

def check_code(addr):
    try:
        req = urllib.request.Request(f"https://studio.genlayer.com/api/contracts/{addr}",
                                      headers={"User-Agent": "Mozilla/5.0"})
        d = json.loads(urllib.request.urlopen(req, timeout=10).read())
        return "data" in d and d["data"] is not None
    except:
        return False

def check_genvm(tx):
    try:
        req = urllib.request.Request(f"https://explorer-studio.genlayer.com/api/transactions/{tx}",
                                      headers={"User-Agent": "Mozilla/5.0"})
        d = json.loads(urllib.request.urlopen(req, timeout=10).read())
        td = d.get("data", d)
        if isinstance(td, dict) and "transaction" in td:
            t = td["transaction"]
            return {
                "status": t.get("status", "?"),
                "genvm": t.get("genvmResult", t.get("genvm_result", "?")) or "?",
                "gas": t.get("gas_used", t.get("gas", "?"))
            }
    except:
        pass
    return {"status": "?", "genvm": "?", "gas": "?"}

# Load clone
clone = open(os.path.join(REPO, "contracts", "test_clone.py")).read()

print("=" * 60)
print("GENVM MUTATION TEST - FINAL")
print("=" * 60)

tests = {}

# Test 0: Clone (OracleNetwork renamed) - KNOWN WORKING
tests[0] = ("clone", clone.replace("class OracleNetwork(gl.Contract):", "class TestClone(gl.Contract):")
                                   .replace("OracleNetwork —", "TestClone —"))

# Test 1: Same as clone but with minimal body
minimal_body = """class TestClone(gl.Contract):
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
"""
tests[1] = ("minimal_body", clone.split("class OracleNetwork(gl.Contract):")[0] + minimal_body)

# Test 2: No dataclasses at all (just like my minimal counter)
tests[2] = ("no_dataclass", """# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

"""Minimal counter."""
from genlayer import *


class TestClone(gl.Contract):
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
""")

# Test 3: OracleNetwork structure but with my exact minimal body
tests[3] = ("oracle_preamble_min_body", clone.split('"""', 2)[0] + '"""\nMinimal counter for GenLayer testing.\n""\n' + 
            "from genlayer import *\n\n\n" + 
            """class TestClone(gl.Contract):
    """Minimal judge contract."""
    OUTLIER_THRESHOLD: u256 = u256(200)
    min_stake: u256 = u256(1000000000000000000)
    count: u256 = u256(0)
    def __init__(self):
        self.count = u256(0)
        self.OUTLIER_THRESHOLD = u256(200)
        self.min_stake = u256(1000000000000000000)
    @gl.public.write
    def increment(self) -> u256:
        self.count += 1
        return self.count
    @gl.public.read
    def get_count(self) -> u256:
        return self.count
""")

for name, source in tests.items():
    print(f"\n[{name[0]}] {name[1]}")
    out = run_deploy(source, f"test_{name[0]}.py")
    info = parse_output(out)
    print(f"  tx={info['tx'][:16] if info['tx'] else 'NONE'}...")
    print(f"  addr={info['addr']}")
    print(f"  exec={info['last_exec']} (all: {info['all_exec']})")
    if info['tx']:
        genvm = check_genvm(info['tx'])
        print(f"  GENVM: status={genvm['status']} result={genvm['genvm']} gas={genvm['gas']}")
    if info['addr']:
        has_code = check_code(info['addr'])
        print(f"  Code stored: {has_code}")
