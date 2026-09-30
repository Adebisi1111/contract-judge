#!/usr/bin/env python3.14
"""Test: is the Depends hash content-dependent? Compute hash and test."""

import subprocess, json, re, os, urllib.request, hashlib

CLI = "/home/administrator/.local/bin/genlayer"
RPC = "https://studio.genlayer.com/api"

def run(source, timeout=200):
    path = "/home/administrator/contract-judge/contracts/exp_test.py"
    with open(path, "w") as f:
        f.write(source)
    cmd = f'echo "test1234" | "{CLI}" deploy --contract "{path}" --rpc {RPC} 2>&1'
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout,
                       cwd="/home/administrator/contract-judge",
                       env=dict(os.environ, HOME=os.path.expanduser("~")))
    return p.stdout

def parse(out):
    tx = re.search(r'(0x[a-fA-F0-9]{64})', out)
    addr = re.search(r"Contract Address': '(0x[a-fA-F0-9]{40})'", out)
    execs = re.findall(r"execution_result: '([^']+)'", out)
    return (tx.group(1) if tx else None, addr.group(1) if addr else None, execs[-1] if execs else '?', execs)

def check_genvm(tx):
    if not tx: return "?"
    try:
        r = urllib.request.urlopen(
            urllib.request.Request(f'https://explorer-studio.genlayer.com/api/transactions/{tx}',
                headers={'User-Agent':'Mozilla/5.0'}), timeout=10)
        d = json.loads(r.read())
        t = d.get('data', d).get('transaction', {})
        g = t.get('genvmResult') or t.get('genvm_result') or '?'
        return f"{t.get('status','?')} | {g[:60]}"
    except: return "ERR"

def check_code(addr):
    if not addr: return False
    try:
        r = urllib.request.urlopen(
            urllib.request.Request(f'https://studio.genlayer.com/api/contracts/{addr}',
                headers={'User-Agent':'Mozilla/5.0'}), timeout=10)
        d = json.loads(r.read())
        return 'data' in d and d['data'] is not None
    except: return False

def t(name, source):
    print(f"\n[{name}]")
    out = run(source)
    tx, addr, exec_res, all_exec = parse(out)
    print(f"  tx={tx[:16] if tx else 'NONE'} addr={addr} exec={exec_res} all={all_exec}")
    if tx:
        print(f"  GENVM={check_genvm(tx)}")
    if addr:
        print(f"  code={check_code(addr)}")

def compute_hash(code):
    """Compute the Depends hash from code. The known working hash is from OracleNetwork."""
    return hashlib.sha256(code.encode()).hexdigest()

# Test: OracleNetwork's exact body with its CORRECT Depends hash
oracle = open("/home/administrator/oracle-network/contracts/oracle_network.py").read()
idx = oracle.find("def register(")
oracle_nome = oracle[:idx]
oracle_nome = oracle_nome.replace("class OracleNetwork(gl.Contract):", "class HashTest(gl.Contract):")
oracle_nome = oracle_nome.replace("OracleNetwork —", "HashTest —")
oracle_full = oracle_nome + "\n    @gl.public.write\n    def register(self) -> str:\n        return 'ok'\n"

# The known correct hash from OracleNetwork
known_hash = "1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6"

# Test 1: OracleNetwork body + its known correct hash
test1 = f'# {{ "Depends": "py-genlayer:{known_hash}" }}\n\n"""Test."""\nfrom genlayer import *\n\n\n{oracle_full}'
t("1_oracle_body_known_hash", test1)

# Test 2: Compute hash of THIS oracle body and use it
h = compute_hash(oracle_full)
print(f"  Computed hash of test body: {h}")
test2 = f'# {{ "Depends": "py-genlayer:{h}" }}\n\n"""Test."""\nfrom genlayer import *\n\n\n{oracle_full}'
t("2_oracle_body_computed_hash", test2)

# Test 3: Minimal counter body + computed hash of THAT body
minimal = (
    '# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }\n'
    '\n'
    '"""Minimal counter."""\n'
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
h_min = compute_hash(minimal)
print(f"  Computed hash of minimal body: {h_min}")
test3 = f'# {{ "Depends": "py-genlayer:{h_min}" }}\n\n"""Test."""\nfrom genlayer import *\n\n\n'
# Remove the old header and append minimal body
min_body = minimal.split('class MinimalJudge(gl.Contract):', 1)[1]
test3 += f'class MinimalJudge(gl.Contract):{min_body}'
t("3_minimal_computed_hash", test3)

print("\nDone.")
