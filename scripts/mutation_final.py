#!/usr/bin/env python3.14
#!/usr/bin/env python3.14
"""Progressive mutation test: find what GENVM rejects."""

import subprocess, json, re, os, urllib.request

REPO = "/home/administrator/contract-judge"
CLI = "/home/administrator/.local/bin/genlayer"
RPC = "https://studio.genlayer.com/api"

def deploy(name, source, timeout=150):
    path = os.path.join(REPO, "contracts", name)
    with open(path, "w") as f:
        f.write(source)
    cmd = f'echo "test1234" | "{CLI}" deploy --contract "{path}" --rpc {RPC} 2>&1'
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout, cwd=REPO, env=dict(os.environ, HOME=os.path.expanduser("~")))
    out = p.stdout
    # Parse output
    tx_m = re.search(r'Transaction Hash.*?: (0x[a-fA-F0-9]+)', out)
    addr_m = re.search(r'Contract Address:\s*(0x[a-fA-F0-9]{40})', out)
    if not tx_m:
        lines = [l.strip() for l in out.splitlines() if l.strip()]
        print(f"  [{name}] FAIL: no tx. Lines: {lines[-3:]}")
        return None
    tx = tx_m.group(1)
    addr = addr_m.group(1) if addr_m else None
    
    # Check GENVM
    status, genvm = "?", "?"
    try:
        req = urllib.request.Request(f"https://explorer-studio.genlayer.com/api/transactions/{tx}",
                                     headers={"User-Agent": "Mozilla/5.0"})
        d = json.loads(urllib.request.urlopen(req, timeout=15).read())
        td = d.get("data", d)
        if isinstance(td, dict) and "transaction" in td:
            t = td["transaction"]
            status = t.get("status", "?")
            genvm = t.get("genvmResult", t.get("genvm_result", "?")) or "?"
            if genvm != "?":
                genvm = genvm[:80]
    except Exception as e:
        status, genvm = "ERR", str(e)[:60]
    
    has_code = False
    if addr:
        try:
            req2 = urllib.request.Request(f"https://studio.genlayer.com/api/contracts/{addr}",
                                          headers={"User-Agent": "Mozilla/5.0"})
            d2 = json.loads(urllib.request.urlopen(req2, timeout=10).read())
            has_code = "data" in d2 and d2["data"] is not None
        except: pass
    
    print(f"  [{name}] tx={tx[:15]}... status={status} genvm={genvm} code={has_code}")
    return {"tx": tx, "addr": addr, "status": status, "genvm": genvm, "code": has_code}

# Load clone
clone = open(os.path.join(REPO, "contracts", "test_clone.py")).read()
class_pos = clone.find("class OracleNetwork(gl.Contract):")

print("=" * 60)
print("GENVM MUTATION TEST - Progressive Simplification")
print("=" * 60)

results = {}
results[0] = deploy("m0_clone.py", clone, 200)

# M1: minimal body
minimal_body = 'class TestClone(gl.Contract):\n    count: u256 = u256(0)\n\n    def __init__(self):\n        self.count = u256(0)\n\n    @gl.public.write\n    def increment(self) -> u256:\n        self.count += 1\n        return self.count\n\n    @gl.public.read\n    def get_count(self) -> u256:\n        return self.count\n'
m1 = clone.split("class OracleNetwork(gl.Contract):")[0] + minimal_body
results[1] = deploy("m1_minimal.py", m1, 200)

# M2: clone body + minimal docstring
body = clone[class_pos:].replace("class OracleNetwork(gl.Contract):", "class TestClone(gl.Contract):")
m2 = clone.split('"""', 1)[0] + '"""\nMinimal.\n"""\n' + body
results[2] = deploy("m2_min_doc.py", m2, 200)

# M3: genlayer only import
m3 = clone.split('"""', 1)[0] + '"""\nMinimal.\n"""\n' + "from genlayer import *\n\n\n" + body
results[3] = deploy("m3_genlayer_only.py", m3, 200)

# M4: no dataclass definitions
body_no_dc = body
for dc_start in [body.find("@allow_storage\n@dataclass\nclass"), body.find("@allow_storage\n@dataclass\nclass")]:
    if dc_start > 0:
        dc_end = body.find("\n\n", body.find("class Request", dc_start))
        if dc_end > 0:
            body_no_dc = body_no_dc[:dc_start] + body_no_dc[dc_end:]
m4 = clone.split('"""', 1)[0] + '"""\nMinimal.\n"""\n' + "from genlayer import *\n\n\n" + body_no_dc
results[4] = deploy("m4_no_dataclass.py", m4, 200)

# M5: no TreeMap fields
m5_body = """@allow_storage
@dataclass
class Record:
    value: u256 = u256(0)
    active: bool = True


class TestClone(gl.Contract):
    \"\"\"Minimal.\"\"\"

    OUTLIER_THRESHOLD: u256 = u256(200)
    count: u256 = u256(0)

    def __init__(self):
        self.count = u256(0)
        self.OUTLIER_THRESHOLD = u256(200)

    @gl.public.write
    def increment(self) -> u256:
        self.count += 1
        return self.count

    @gl.public.read
    def get_count(self) -> u256:
        return self.count
"""
m5 = clone.split('"""', 1)[0] + '"""\nMinimal.\n"""\n' + "from genlayer import *\n\n\n" + m5_body
results[5] = deploy("m5_no_treemap.py", m5, 200)

# M6: remove class-level constants
m6_body = """@allow_storage
@dataclass
class Record:
    value: u256 = u256(0)
    active: bool = True


class TestClone(gl.Contract):
    \"\"\"Minimal.\"\"\"

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
m6 = clone.split('"""', 1)[0] + '"""\nMinimal.\n"""\n' + "from genlayer import *\n\n\n" + m6_body
results[6] = deploy("m6_no_constants.py", m6, 200)

# M7: no class docstring at all
m7_body = """@allow_storage
@dataclass
class Record:
    value: u256 = u256(0)
    active: bool = True


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
"""
m7 = clone.split('"""', 1)[0] + '"""\nMinimal.\n"""\n' + "from genlayer import *\n\n\n" + m7_body
results[7] = deploy("m7_no_class_doc.py", m7, 200)

# M8: no dataclass _at all_  
m8_body = """class TestClone(gl.Contract):
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
m8 = clone.split('"""', 1)[0] + '"""\nMinimal.\n"""\n' + "from genlayer import *\n\n\n" + m8_body
results[8] = deploy("m8_no_dataclass_class.py", m8, 200)

# M9: absolute minimal (no docstring in file at all, just code)
m9 = """# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

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
"""
results[9] = deploy("m9_abs_minimal.py", m9, 200)

# M10: same as M9 but with blank line before class
m10 = """# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

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
"""
results[10] = deploy("m10_blank_before_class.py", m10, 200)

# M11: OracleNetwork clone EXACT (no modifications at all)
results[11] = deploy("m11_exact_clone.py", clone.replace("class OracleNetwork(gl.Contract):", "class TestClone(gl.Contract):").replace("OracleNetwork —", "TestClone —"), 200)

print("\n" + "=" * 60)
print("RESULTS SUMMARY")
print("=" * 60)
names = ["clone(rename)", "minimal_body", "min_doc_full_body", "genlayer_only_import", 
         "no_dataclass_defs", "no_treemap", "no_constants", "no_class_doc", 
         "no_dataclass_at_all", "abs_minimal", "blank_before_class", "exact_clone"]
for i, (name, r) in enumerate(results.items()):
    if r:
        print(f"  [{i}] {names[i]:25s} → status={r['status']} genvm={str(r['genvm'])[:40]} code={r['code']}")
    else:
        print(f"  [{i}] {names[i]:25s} → FAILED/NO_TX")
