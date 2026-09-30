#!/usr/bin/env python3.14
"""FINAL controlled experiment - fix syntax."""

import subprocess, json, re, os, urllib.request

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
    addr_match = re.search(r"Contract Address': '(0x[a-fA-F0-9]{40})'", out)
    execs = re.findall(r"execution_result: '([^']+)'", out)
    addr = addr_match.group(1) if addr_match else None
    return (tx.group(1) if tx else None, addr, execs[-1] if execs else '?')

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
    tx, addr, exec_res = parse(out)
    print(f"  tx={tx[:16] if tx else 'NONE'} addr={addr} exec={exec_res}")
    if tx:
        print(f"  GENVM={check_genvm(tx)}")
    if addr:
        print(f"  code={check_code(addr)}")

# Test 1: Base minimal (FAILS)
base = (
    '# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }\n'
    '\n'
    '"""Minimal counter for GenLayer testing."""\n'
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
t("1_base_failing", base)

# Test 2: With @allow_storage on class
t2 = base.replace("class MinimalJudge(gl.Contract):", "@allow_storage\nclass MinimalJudge(gl.Contract):")
t("2_allow_storage_on_class", t2)

# Test 3: Minimal body + OracleNetwork dataclass
t3 = ("# { \"Depends\": \"py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6\" }\n"
      '\nfrom genlayer import *\nfrom dataclasses import dataclass\n'
      '\n\n'
      '@allow_storage\n'
      '@dataclass\n'
      'class CounterRecord:\n'
      '    count: u256 = u256(0)\n'
      '\n\n'
      'class Test3(gl.Contract):\n'
      '    """Test contract."""\n'
      '    records: TreeMap[str, CounterRecord]\n'
      '    def __init__(self):\n'
      '        pass\n'
      '    @gl.public.write\n'
      '    def inc(self) -> u256:\n'
      '        return u256(1)\n')
t("3_with_dataclass", t3)

# Test 4: OracleNetwork body stripped to minimal
oracle = open("/home/administrator/oracle-network/contracts/oracle_network.py").read()
# Keep the dataclasses, TreeMap fields, class constants, __init__, but replace methods with minimal
oracle_min = oracle.split("def register(")[0]  # Keep everything up to first method
oracle_min = oracle_min.replace("class OracleNetwork(gl.Contract):", "class Test4(gl.Contract):")
oracle_min = oracle_min.replace("OracleNetwork —", "Test4 —")
t("4_oracle_up_to_first_method", oracle_min)

# Test 5: OracleNetwork with ALL methods replaced by stubs
# Find the class definition and everything up to first method
idx = oracle.find("def register(")
class_and_fields = oracle[:idx]
class_and_fields = class_and_fields.replace("class OracleNetwork(gl.Contract):", "class Test5(gl.Contract):")
class_and_fields = class_and_fields.replace("OracleNetwork —", "Test5 —")
# Add minimal method stub
oracle_stub = class_and_fields + "\n    @gl.public.write\n    def register(self) -> None:\n        pass\n"
t("5_oracle_with_stub_method", oracle_stub)

print("\nDone.")
