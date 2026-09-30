#!/usr/bin/env python3.14
"""Controlled experiment: add OracleNetwork features to minimal counter one at a time."""

import subprocess, json, re, os, urllib.request

CLI = "/home/administrator/.local/bin/genlayer"
RPC = "https://studio.genlayer.com/api"

def run(source, name, timeout=200):
    path = f"/home/administrator/contract-judge/contracts/{name}.py"
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
    if not tx: return ("?", "?", "?")
    try:
        r = urllib.request.urlopen(
            urllib.request.Request(f'https://explorer-studio.genlayer.com/api/transactions/{tx}',
                headers={'User-Agent':'Mozilla/5.0'}), timeout=10)
        d = json.loads(r.read())
        t = d.get('data', d).get('transaction', {})
        g = t.get('genvmResult') or t.get('genvm_result') or '?'
        return (t.get('status','?'), g[:80] if g != '?' else '?', t.get('gas_used', t.get('gas','?')))
    except Exception as e:
        return ("ERR", str(e)[:80], "?")

def check_code(addr):
    if not addr: return False
    try:
        r = urllib.request.urlopen(
            urllib.request.Request(f'https://studio.genlayer.com/api/contracts/{addr}',
                headers={'User-Agent':'Mozilla/5.0'}), timeout=10)
        d = json.loads(r.read())
        return 'data' in d and d['data'] is not None
    except: return False

def test(name, source):
    print(f"\n[{name}]")
    out = run(source, f"exp_{name}")
    tx, addr, last_exec, all_exec = parse(out)
    print(f"  tx={tx[:16] if tx else 'NONE'} addr={addr} exec={last_exec} all_exec={all_exec}")
    if tx:
        s, g, gas = check_genvm(tx)
        print(f"  GENVM: status={s} result={g} gas={gas}")
    if addr:
        print(f"  code_stored={check_code(addr)}")

# Base: minimal counter (FAILS)
base = ("# { \"Depends\": \"py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6\" }\n"
        '\n'
        '"""Minimal counter for GenLayer testing."""\n'
        'from genlayer import *\n'
        '\n'
        '\n'
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
        '        return self.count\n')

# Test 1: Base (EXPECTED TO FAIL)
test("1_base_failing", base)

# Test 2: Add import json
test("2_add_json", base.replace("from genlayer import *", "import json\nfrom genlayer import *"))

# Test 3: Add multi-line docstring
test("3_add_multiline_doc", base.replace('"""Minimal counter for GenLayer testing."""',
    '"""Minimal counter for GenLayer testing.\n========================================\n"""'))

# Test 4: Add class docstring
test("4_add_class_doc", base.replace("class MinimalJudge(gl.Contract):",
    'class MinimalJudge(gl.Contract):\n    """Minimal judge contract."""'))

# Test 5: Add class-level constant
test("5_add_class_constant", base.replace(
    "class MinimalJudge(gl.Contract):\n    count: u256 = u256(0)",
    'class MinimalJudge(gl.Contract):\n    OUTLIER_THRESHOLD: u256 = u256(200)\n    count: u256 = u256(0)'))

# Test 6: All preamble features combined
combined = base.replace('"""Minimal counter for GenLayer testing."""',
    '"""Minimal counter for GenLayer testing.\n========================================\n"""')
combined = combined.replace("from genlayer import *", "import json\nfrom genlayer import *")
combined = combined.replace("class MinimalJudge(gl.Contract):\n    count: u256 = u256(0)",
    'class MinimalJudge(gl.Contract):\n    """Minimal judge contract."""\n    OUTLIER_THRESHOLD: u256 = u256(200)\n    count: u256 = u256(0)')
test("6_all_preamble_features", combined)

# Test 7: OracleNetwork EXACT preamble + minimal body
oracle_preamble = open("/home/administrator/oracle-network/contracts/oracle_network.py").read()
oracle_preamble = oracle_preamble.split('class OracleNetwork(gl.Contract):')[0]
oracle_preamble = oracle_preamble.replace("OracleNetwork —", "TestClone —")
minimal_body = ("class TestClone(gl.Contract):\n"
               '    """Minimal judge contract."""\n'
               '    count: u256 = u256(0)\n'
               '    def __init__(self):\n'
               '        self.count = u256(0)\n'
               '    @gl.public.write\n'
               '    def increment(self) -> u256:\n'
               '        self.count += 1\n'
               '        return self.count\n'
               '    @gl.public.read\n'
               '    def get_count(self) -> u256:\n'
               '        return self.count\n')
test("7_oracle_preamble", oracle_preamble + minimal_body)

print("\nDone.")
