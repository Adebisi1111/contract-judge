import subprocess, json, sys

GPS = "/home/administrator/.local/bin/genlayer"
RPC = "https://studio.genlayer.com/api"
PASSWORD = "test1234"

def deploy(contract_path, label):
    cmd = f'echo "{PASSWORD}" | {GPS} deploy --rpc {RPC} --contract {contract_path}'
    print(f"\n{'='*60}")
    print(f"Deploying {label} ({contract_path})...")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
    output = result.stdout + result.stderr
    
    # Extract transaction hash
    tx_hash = None
    contract_addr = None
    for line in output.split('\n'):
        if 'Transaction Hash:' in line:
            tx_hash = line.split(': ')[-1].strip()
        if 'Contract Address:' in line and 'Result:' not in line:
            contract_addr = line.split(': ')[-1].strip()
    
    # Check on-chain via gen_getContractCode
    if contract_addr:
        check_cmd = ['curl', '-s', '-X', 'POST', RPC,
                     '-H', 'Content-Type: application/json',
                     '-d', json.dumps({
                         "jsonrpc": "2.0",
                         "method": "gen_getContractCode",
                         "params": [contract_addr],
                         "id": 1
                     })]
        check_result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=10)
        try:
            resp = json.loads(check_result.stdout)
            code = resp.get('result', '')
            status = "✅ ON-CHAIN" if code else "❌ NOT FOUND"
            print(f"  Transaction: {tx_hash}")
            print(f"  Contract:    {contract_addr}")
            print(f"  On-chain:    {status} ({len(code)} chars)")
        except:
            print(f"  Transaction: {tx_hash}")
            print(f"  Contract:    {contract_addr}")
            print(f"  On-chain:    ??? (check failed)")
    else:
        print(f"  Deploy output (last 500 chars):")
        print(output[-500:])
    
    return contract_addr

results = {}
results['judge'] = deploy('contracts/judge_contract.py', 'ContractJudge')
results['minimal'] = deploy('contracts/minimal.py', 'MinimalCounter')

print(f"\n{'='*60}")
print("SUMMARY:")
for name, addr in results.items():
    print(f"  {name}: {addr or 'FAILED'}")
