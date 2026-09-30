#!/usr/bin/env python3.14
"""Debug script: compile ContractJudge, call GENVM simulate, show errors."""

import os, sys, subprocess, json, re, base64, hashlib, zlib

REPO = "/home/administrator/contract-judge"
CTOR = os.path.join(REPO, "contracts/judge_contract.py")
CLI = "/home/administrator/.local/bin/genlayer"
SDK = os.path.join(REPO, "node_modules/genlayer-js/dist/index.js")

os.environ["HOME"] = os.path.expanduser("~")

def run(cmd, timeout=300):
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=REPO, env=os.environ)
    try:
        stdout, stderr = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        p.kill()
        stdout, stderr = p.communicate()
        return stdout.decode(errors="replace"), stderr.decode(errors="replace"), -1
    return stdout.decode(errors="replace"), stderr.decode(errors="replace"), p.returncode

# Step 1: Generate keys and deploy via CLI
print("=== Step 1: Deploy via genlayer CLI ===")
out, err, rc = run(f'echo "test1234" | "{CLI}" deploy --contract "{CTOR}" --rpc https://studio.genlayer.com/api', timeout=300)
print(f"rc={rc}")
for line in err.splitlines():
    if line.strip(): print("ERR:", line)
for line in out.splitlines():
    if "ERROR" in line or "execution_result" in line:
        print("OUT:", line[:200])
    if "Contract Address" in line:
        m = re.search(r"0x[a-fA-F0-9]{40}", out)
        if m:
            addr = m.group(0)
            print(f"\n=== Contract Address: {addr} ===")
            # Try getContractCode
            print("\n=== Step 2: gen_getContractCode ===")
            import urllib.request
            payload = json.dumps({"jsonrpc":"2.0","id":1,"method":"gen_getContractCode","params":[addr]}).encode()
            req = urllib.request.Request("https://studio.genlayer.com/api", data=payload, headers={"Content-Type":"application/json"})
            try:
                resp = urllib.request.urlopen(req, timeout=30)
                data = json.loads(resp.read())
                result = data.get("result","")
                if result:
                    code = base64.b64decode(result).decode("utf-8","replace")
                    print(f"CODE LENGTH: {len(code)}")
                    print(code[:600])
                else:
                    print("No code returned:", json.dumps(data)[:300])
            except Exception as e:
                print("API error:", e)

# Step 3: Read contract source and simulate what GENVM might check
print("\n=== Step 3: Contract source analysis ===")
with open(CTOR) as f:
    source = f.read()

# Check for GENVM-invalid patterns
issues = []
if "gl.eq_principle" in source:
    issues.append("- Uses gl.eq_principle (may not be supported in GENVM)")
if "gl.nondet.exec_prompt" in source:
    issues.append("- Uses gl.nondet.exec_prompt (nondeterministic - requires GENVM support)")
if "def __init__" in source and "self." in source.split("def __init__")[1].split("def ")[0]:
    issues.append("- Has __init__ with instance variable assignments")
if "@allow_storage" in source:
    issues.append("- Uses @allow_storage decorator")
if "@dataclass" in source:
    issues.append("- Uses @dataclass decorator")

print("Potential issues found:")
for i in issues:
    print(i)
if not issues:
    print("  (none)")

# Check bytecode simulation
print("\n=== Step 4: Check Node.js genlayer-js module structure ===")
try:
    with open(os.path.join(REPO, "node_modules/genlayer-js/package.json")) as f:
        pkg = json.load(f)
    print(f"genlayer-js version: {pkg.get('version','?')}")
except:
    print("Could not read genlayer-js package.json")

print("\nDone.")
