#!/usr/bin/env python3.14
"""Progressive mutation test: start with OracleNetwork clone (works),
progressively simplify until GENVM breaks."""

import subprocess, json, re, os, urllib.request

REPO = "/home/administrator/contract-judge"
CLI = "/home/administrator/.local/bin/genlayer"
RPC = "https://studio.genlayer.com/api"
HOME = os.path.expanduser("~")

def get_genvm_result(tx_hash):
    try:
        req = urllib.request.Request(
            f"https://explorer-studio.genlayer.com/api/transactions/{tx_hash}",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        tx_resp = json.loads(urllib.request.urlopen(req, timeout=15).read())
        tx_data = tx_resp.get("data", tx_resp)
        if isinstance(tx_data, dict) and "transaction" in tx_data:
            tx = tx_data["transaction"]
            result = tx.get("genvmResult", tx.get("genvm_result", "N/A"))
            status = tx.get("status", "N/A")
            return status, result
    except Exception as e:
        return "ERROR", str(e)[:100]
    return "ERROR", "no response"

def deploy_and_check(source_code, test_name, timeout=150):
    path = os.path.join(REPO, "contracts", f"mutate_{test_name}.py")
    with open(path, "w") as f:
        f.write(source_code)
    cmd = f'echo "test1234" | "{CLI}" deploy --contract "{path}" --rpc {RPC}'
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout, cwd=REPO, env={**os.environ, "HOME": HOME})
    out = p.stdout + p.stderr
    if "Enter password" in out:
        print(f"  [{test_name}] FAILED: password prompt not handled")
        return None
    
    tx_m = re.search(r'Transaction Hash.*?: (0x[a-fA-F0-9]+)', out)
    if not tx_m:
        print(f"  [{test_name}] No tx hash. rc={p.returncode}")
        for line in out.splitlines():
            if "ERROR" in line or "execution_result" in line or "Contract" in line:
                print(f"    {line.strip()}")
        return None
    
    tx_hash = tx_m.group(1)
    status, genvm = get_genvm_result(tx_hash)
    has_code = False
    addr_m = re.search(r'Contract Address:\s*(0x[a-fA-F0-9]{40})', out)
    if addr_m:
        addr = addr_m.group(1)
        try:
            req3 = urllib.request.Request(
                f"https://studio.genlayer.com/api/contracts/{addr}",
                headers={"User-Agent": "Mozilla/5.0"}
            )
            resp3 = urllib.request.urlopen(req3, timeout=10).read()
            d3 = json.loads(resp3)
            if "data" in d3 and d3.get("data") is not None:
                has_code = True
        except: pass
    
    print(f"  [{test_name}] tx={tx_hash[:16]}... status={status} genvm={genvm[:50] if genvm else 'None'} has_code={has_code}")
    return {"tx": tx_hash, "status": status, "genvm": genvm, "has_code": has_code}

# Load clone source
clone_src = open(os.path.join(REPO, "contracts", "test_clone.py")).read()
class_start = clone_src.find("class OracleNetwork(gl.Contract):")

print("=" * 60)
print("PROGRESSIVE MUTATION TEST")
print("=" * 60)

print("\n[0] Base: OracleNetwork clone with renamed class (KNOWN WORKING)")
deploy_and_check(clone_src, "clone")

# Mutation 1: Same preamble, minimal body
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
mutation1 = clone_src.split("class OracleNetwork(gl.Contract):")[0] + minimal_body
print("\n[1] Minimal body (count: u256) + same preamble")
deploy_and_check(mutation1, "minimal_body")

# Mutation 2: Minimal docstring + same body as clone
class_part = clone_src[class_start:].replace("class OracleNetwork(gl.Contract):", "class TestClone(gl.Contract):")
mutation2 = clone_src.split('"""', 1)[0] + '"""\nMinimal.\n"""\n' + class_part
print("\n[2] Minimal docstring + full clone body")
deploy_and_check(mutation2, "minimal_doc")

# Mutation 3: No dataclasses, keep class storage
mutation3 = clone_src.split('"""', 1)[0] + '"""\nMinimal.\n"""\n'
mutation3 += "from genlayer import *\n\n\n"
idx_after_class = class_part.find("@gl.public.write")
if idx_after_class == -1:
    idx_after_class = class_part.find("@gl.public.read")
mutation3 += class_part[:idx_after_class]
mutation3 += '    @gl.public.write\n    def increment(self) -> u256:\n        self.min_stake += u256(1)\n        return self.min_stake\n\n    @gl.public.read\n    def get_count(self) -> u256:\n        return self.min_stake\n'
print("\n[3] Remove dataclasses, keep class storage")
deploy_and_check(mutation3, "no_dataclasses")

# Mutation 4: Remove TreeMap storage
mutation4 = clone_src.split('"""', 1)[0] + '"""\nMinimal.\n"""\n'
mutation4 += "from genlayer import *\n\n\n"
mutation4 += "class TestClone(gl.Contract):\n    \"\"\"Minimal.\"\"\"\n\n    OUTLIER_THRESHOLD: u256 = u256(200)\n    count: u256 = u256(0)\n\n    def __init__(self):\n        self.count = u256(0)\n        self.OUTLIER_THRESHOLD = u256(200)\n\n    @gl.public.write\n    def increment(self) -> u256:\n        self.count += 1\n        return self.count\n\n    @gl.public.read\n    def get_count(self) -> u256:\n        return self.count\n"
print("\n[4] No TreeMap, only plain fields")
deploy_and_check(mutation4, "no_treemap")

# Mutation 5: Remove class-level constants (OUTLIER_THRESHOLD)
mutation5 = clone_src.split('"""', 1)[0] + '"""\nMinimal.\n"""\n'
mutation5 += "from genlayer import *\n\n\n"
mutation5 += "class TestClone(gl.Contract):\n    \"\"\"Minimal.\"\"\"\n\n    count: u256 = u256(0)\n\n    def __init__(self):\n        self.count = u256(0)\n\n    @gl.public.write\n    def increment(self) -> u256:\n        self.count += 1\n        return self.count\n\n    @gl.public.read\n    def get_count(self) -> u256:\n        return self.count\n"
print("\n[5] No class-level constants, minimal fields")
deploy_and_check(mutation5, "no_constants")

# Mutation 6: Add @allow_storage to class (like OracleNetwork has on dataclasses)
mutation6 = clone_src.split('"""', 1)[0] + '"""\nMinimal.\n"""\n'
mutation6 += "from genlayer import *\n\n\n"
mutation6 += "@allow_storage\nclass TestClone(gl.Contract):\n    \"\"\"Minimal.\"\"\"\n\n    count: u256 = u256(0)\n\n    def __init__(self):\n        self.count = u256(0)\n\n    @gl.public.write\n    def increment(self) -> u256:\n        self.count += 1\n        return self.count\n\n    @gl.public.read\n    def get_count(self) -> u256:\n        return self.count\n"
print("\n[6] Add @allow_storage to class")
deploy_and_check(mutation6, "allow_storage")

print("\n=== SUMMARY ===")
print("[0] clone → works → GENVM accepts OracleNetwork structure")
for i in range(1, 7):
    print(f"[{i}] mutation → check if still works")
print("The first mutation that BREAKS tells us what GENVM rejects")
