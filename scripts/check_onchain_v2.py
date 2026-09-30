import subprocess, json, time, sys

GPS = "/home/administrator/.local/bin/genlayer"
RPC = "https://studio.genlayer.com/api"
PASSWORD = "test1234"

def wait_for_onchain(addr, timeout=60, interval=5):
    """Poll gen_getContractCode until code appears or timeout."""
    start = time.time()
    while time.time() - start < timeout:
        cmd = ['curl', '-s', '-X', 'POST', RPC,
               '-H', 'Content-Type: application/json',
               '-d', json.dumps({
                   "jsonrpc": "2.0",
                   "method": "gen_getContractCode",
                   "params": [addr],
                   "id": 1
               })]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        try:
            resp = json.loads(result.stdout)
            code = resp.get('result', '')
            if code:
                return True, len(code)
        except:
            pass
        time.sleep(interval)
    return False, 0

def deploy_and_verify(contract_path, label):
    print(f"\n{'='*60}")
    print(f"Deploying {label} ({contract_path})...")
    
    cmd = f'echo "{PASSWORD}" | {GPS} deploy --rpc {RPC} --contract {contract_path}'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
    output = result.stdout + result.stderr
    
    # Extract contract address
    contract_addr = None
    for line in output.split('\n'):
        if 'Contract Address:' in line and 'Result:' not in line:
            contract_addr = line.split(': ')[-1].strip()
            break
    
    if not contract_addr:
        print(f"  ❌ Failed to extract contract address")
        print(f"  Last 300 chars: {output[-300:]}")
        return None
    
    print(f"  Transaction sent. Contract: {contract_addr}")
    print(f"  Waiting for on-chain confirmation...")
    
    found, size = wait_for_onchain(contract_addr, timeout=90, interval=5)
    
    if found:
        print(f"  ✅ ON-CHAIN confirmed: {size} chars of bytecode")
    else:
        print(f"  ❌ NOT FOUND after 90s polling")
    
    return contract_addr, found

print("=" * 60)
print("CONTRACT JUDGE — ON-CHAIN VERIFICATION")
print("=" * 60)

judge_result = deploy_and_verify('contracts/judge_contract.py', 'ContractJudge')
minimal_result = deploy_and_verify('contracts/minimal.py', 'MinimalCounter')

print(f"\n{'='*60}")
print("FINAL SUMMARY:")
print(f"  ContractJudge: {judge_result[0] if judge_result else 'FAILED'} — {'✅' if judge_result and judge_result[1] else '❌'}")
print(f"  MinimalCounter: {minimal_result[0] if minimal_result else 'FAILED'} — {'✅' if minimal_result and minimal_result[1] else '❌'}")
