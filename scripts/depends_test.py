#!/usr/bin/env python3.14
"""Test: does the Depends header hash matter? Test with wrong hash."""

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
    addr = re.search(r"Contract Address': '(0x[a-fA-F0-9]{40})'", out)
    execs = re.findall(r"execution_result: '([^']+)'", out)
    return (tx.group(1) if tx else None, addr.group(1) if addr else None, execs[-1] if execs else '?')

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

# The working OracleNetwork clone body (with stub method)
oracle = open("/home/administrator/oracle-network/contracts/oracle_network.py").read()
idx = oracle.find("def register(")
class_and_fields = oracle[:idx]
class_and_fields = class_and_fields.replace("class OracleNetwork(gl.Contract):", "class TestKey(gl.Contract):")
class_and_fields = class_and_fields.replace("OracleNetwork —", "TestKey —")
working_body = class_and_fields + "\n    @gl.public.write\n    def register(self) -> None:\n        pass\n"

# Test 1: Working body with CORRECT Depends hash (should SUCCEED)
correct_header = ('# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }\n\n"""Test."""\nfrom genlayer import *\n\n\n')
test1 = correct_header + working_body
t("1_correct_hash", test1)

# Test 2: Working body with WRONG Depends hash
wrong_header = ('# { "Depends": "py-genlayer:WRONG_HASH_1234567890abcdef" }\n\n"""Test."""\nfrom genlayer import *\n\n\n')
test2 = wrong_header + working_body
t("2_wrong_hash", test2)

# Test 3: Working body with NO Depends header
no_header = ('"""Test."""\nfrom genlayer import *\n\n\n')
test3 = no_header + working_body
t("3_no_header", test3)

# Test 4: Working body with empty Depends
empty_header = ('# { "Depends": "" }\n\n"""Test."""\nfrom genlayer import *\n\n\n')
test4 = empty_header + working_body
t("4_empty_hash", test4)

print("\nDone.")
