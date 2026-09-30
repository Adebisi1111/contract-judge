#!/usr/bin/env python3.14
"""
Final report: explains why all ContractJudge attempts fail GENVM validation.
"""

import subprocess, json, re, os, urllib.request, hashlib, base64

CLI = "/home/administrator/.local/bin/genlayer"
RPC = "https://studio.genlayer.com/api"
HOME = os.path.expanduser("~")

def deploy(source, name, timeout=200):
    path = f"/home/administrator/contract-judge/contracts/{name}.py"
    with open(path, "w") as f:
        f.write(source)
    cmd = f'echo "test1234" | "{CLI}" deploy --contract "{path}" --rpc {RPC} 2>&1'
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout,
                       cwd="/home/administrator/contract-judge",
                       env=dict(os.environ, HOME=HOME))
    return p.stdout

def parse(out):
    tx = re.search(r'(0x[a-fA-F0-9]{64})', out)
    addr = re.search(r"Contract Address': '(0x[a-fA-F0-9]{40})'", out)
    execs = re.findall(r"execution_result: '([^']+)'", out)
    return (tx.group(1) if tx else None, addr.group(1) if addr else None, execs)

def raw_genvm_result(tx_hash):
    """Get the RAW bytes of the GENVM result from a transaction."""
    try:
        # Try JSON-RPC API first
        payload = json.dumps({
            "jsonrpc": "2.0", "id": 1,
            "method": "eth_call",
            "params": [{"to": tx_hash, "data": "0x"}]
        }).encode()
        req = urllib.request.Request(RPC, data=payload,
                                      headers={"Content-Type": "application/json",
                                               "User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        d = json.loads(resp.read())
        if "error" in d:
            return None, f"RPC error: {d['error']}"
        result = d.get("result", "0x")
        if result == "0x" or result == "":
            return None, "empty result"
        # Decode hex result
        hex_str = result[2:] if result.startswith("0x") else result
        raw = bytes.fromhex(hex_str)
        return raw, None
    except Exception as e:
        return None, str(e)

def check_code(addr):
    try:
        r = urllib.request.urlopen(
            urllib.request.Request(f"https://studio.genlayer.com/api/contracts/{addr}",
                headers={"User-Agent": "Mozilla/5.0"}), timeout=10)
        d = json.loads(r.read())
        return "data" in d and d["data"] is not None
    except: return False

# ===========================================================================
# PART 1: The Known Working Case
# ===========================================================================
print("=" * 70)
print("PART 1: ORACLE NETWORK (known working, 0xCF6c... on studio)")
print("=" * 70)

oracle_addr = "0xCF6c25af72A7997C591146B946101D736A4d6bB0"
code = check_code(oracle_addr)
print(f"Code stored at {oracle_addr}: {code}")
if code:
    print("  → This contract HAS bytecode on-chain")
else:
    print("  → No bytecode (contract not found)")

# ===========================================================================
# PART 2: Deployment of OracleNetwork clone
# ===========================================================================
print()
print("=" * 70)
print("PART 2: Deploy OracleNetwork clone (known working source)")
print("=" * 70)

oracle_src = open("/home/administrator/oracle-network/contracts/oracle_network.py").read()
out = deploy(oracle_src, "final_oracle_clone")
tx, addr, execs = parse(out)
print(f"Transaction: {tx}")
print(f"Contract address: {addr}")
print(f"Execution results: {execs}")

# ===========================================================================
# PART 3: My minimal counter (FAILS)
# ===========================================================================
print()
print("=" * 70)
print("PART 3: Deploy minimal counter (FAILS)")
print("=" * 70)

minimal_src = (
    '# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }\n'
    '\n"""Minimal counter for GenLayer testing."""\n'
    'from genlayer import *\n'
    '\n\n'
    'class MinimalJudge(gl.Contract):\n'
    '    count: u256 = u256(0)\n'
    '    def __init__(self):\n'
    '        self.count = u256(0)\n'
    '    @gl.public.write\n'
    '    def increment(self) -> u256:\n'
    '        self.count += 1\n'
    '        return self.count\n'
    '    @gl.public.read\n'
    '    def get_count(self) -> u256:\n'
    '        return self.count\n'
)
out = deploy(minimal_src, "final_minimal")
tx, addr, execs = parse(out)
print(f"Transaction: {tx}")
print(f"Contract address: {addr}")
print(f"Execution results: {execs}")
print(f"Code stored: {check_code(addr)}")

# ===========================================================================
# PART 4: Key Insight
# ===========================================================================
print()
print("=" * 70)
print("PART 4: KEY INSIGHT — WHY MINIMAL FAILS AND ORACLE WORKS")
print("=" * 70)

print("""
The GENVM returns exit_code 1 for my contracts but success for OracleNetwork.

CRITICAL FINDING from depends_test.py:
  - Test 1: OracleNetwork body + CORRECT Depends hash → SUCCESS
  - Test 2: OracleNetwork body + WRONG Depends hash → ERROR  
  - Test 3: OracleNetwork body + NO Depends header → ERROR
  - Test 4: OracleNetwork body + EMPTY Depends hash → ERROR

  → The Depends hash MUST be "1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6"
  → This hash IDENTIFIES the py-genlayer runtime version on the network

CRITICAL FINDING from hash_test.py:
  - Test 1: OracleNetwork body + known correct hash → SUCCESS (mixed: 4 SUCCESS, 2 ERROR)
  - Test 2: OracleNetwork body + freshly computed SHA256 hash → ERROR (all 6)
  - Test 3: Minimal counter + computed hash of itself → ERROR (all 6)

  → The Depends hash is NOT computed from the source code
  → It is a PRE-COMPUTED identifier hardcoded in the contract
  → Using a computed hash produces a DIFFERENT hash than what GENVM expects

THE ROOT CAUSE:
  My contracts ALL fail because they use a Depends hash that GENVM rejects.
  The hash "1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" works for
  OracleNetwork because that's the hash OracleNetwork was deployed with.
  
  BUT: even with the CORRECT hash, my minimal counter STILL fails.
  This means there are TWO separate issues:
  
  ISSUE 1: The Depends hash — must match what's on the network
  ISSUE 2: The contract BODY — GENVM rejects minimal contracts
  
  The body issue is the harder one. OracleNetwork's complex body works.
  My minimal counter body fails even with the correct hash.
  
  The GENVM likely validates the contract bytecode structure and rejects
  contracts that are "too simple" or lack certain required features.
  OracleNetwork has: dataclasses, TreeMaps, multiple methods, class 
  constants, resolve() with genvm features — my minimal counter has none.
""")

# ===========================================================================
# PART 5: What We Know Works
# ===========================================================================
print()
print("=" * 70)
print("PART 5: WHAT ACTUALLY WORKS")
print("=" * 70)

print("""
FRONTEND (fully working):
  - React + Vite + Tailwind CSS at localhost:5173
  - Static analysis: identifies security issues in submitted code
  - Sample contracts: Valid, NoImport, BareExcept
  - Analysis results: issues list with severity, line numbers, descriptions
  - GitHub Pages deployed: https://adébisi1111.github.io/contract-judge/
  - Git repo: github.com/Adebisi1111/contract-judge (main branch)

WHAT'S NOT WORKING:
  - GenLayer contract deployment: EVERY contract I write gets GENVM exit_code 1
  - Even the simplest possible contract (bare u256 counter) fails
  - OracleNetwork copy (byte-for-byte) deploys with SUCCESS
  - The difference is in the contract BODY, not the deployment process
  
GENVM BEHAVIOR:
  - exit_code 0 (\\x00\\x00) = success, bytecode stored
  - exit_code 1 (\\x02 + "exit_code 1") = rejection, no bytecode
  - My contracts consistently get exit_code 1
  - OracleNetwork clone gets exit_code 0

CONTRACTS THAT FAIL (all with exit_code 1):
  - Minimal counter: just count: u256, increment(), get_count()
  - Counter + delegation
  - Counter + TreeMap[str, str]
  - Counter + TreeMap[str, Submission]
  - Counter + allow_storage + dataclass + TreeMap
  - Any variant with/without imports, docstrings, class constants
  
CONTRACTS THAT WORK (exit_code 0):
  - OracleNetwork (byte-for-byte copy): complex with dataclasses, TreeMaps,
    multiple methods, class constants, resolve() with genvm features
""")
