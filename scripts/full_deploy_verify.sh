#!/bin/bash
# Full deploy + on-chain verification for ContractJudge
set -e

PASSWORD="test1234"
GPS="/home/administrator/.local/bin/genlayer"
RPC="https://studio.genlayer.com/api"

log() { echo "[$(date '+%H:%M:%S')] $*"; }

deploy_and_verify() {
    local contract="$1"
    local label="$2"
    log "========================================"
    log "Deploying $label: $contract"
    log "========================================"
    
    # Deploy with timeout
    output=$(echo "$PASSWORD" | $GPS deploy --rpc "$RPC" --contract "$contract" 2>&1)
    echo "$output"
    
    # Extract addresses
    addr=$(echo "$output" | grep "contract_address:" | head -1 | sed "s/.*contract_address: '//;s/'.*//")
    tx=$(echo "$output" | grep "Transaction Hash:" | tail -1 | sed "s/.*Transaction Hash: '//;s/'.*//")
    
    log ""
    log "Transaction: $tx"
    log "Contract:    $addr"
    
    if [ -z "$addr" ] || [ "$addr" = "" ]; then
        log "ERROR: Could not extract contract address from deploy output"
        return 1
    fi
    
    # Wait for on-chain (poll up to 90s)
    log "Waiting for on-chain confirmation..."
    for i in $(seq 1 18); do
        code=$(curl -s -X POST "$RPC" \
            -H "Content-Type: application/json" \
            -d "{\"jsonrpc\":\"2.0\",\"method\":\"gen_getContractCode\",\"params\":[\"$addr\"],\"id\":1}" 2>&1 | \
            python3.14 -c "import sys,json; d=json.load(sys.stdin); print(d.get('result',''))" 2>/dev/null)
        
        if [ -n "$code" ]; then
            size=$(echo -n "$code" | wc -c)
            log "ON-CHAIN confirmed after ~$((i*5))s — $size bytes"
            log "First 150 chars: $(echo "$code" | head -c 150)"
            echo "$addr"
            return 0
        fi
        sleep 5
    done
    
    log "NOT FOUND after 90s polling"
    return 1
}

# Main
log "CONTRACT JUDGE — FULL DEPLOY + VERIFY"
log "======================================"

judge_addr=$(deploy_and_verify "contracts/judge_contract.py" "ContractJudge")
judge_ok=$?

minimal_addr=$(deploy_and_verify "contracts/minimal.py" "MinimalCounter")
minimal_ok=$?

log ""
log "========================================"
log "FINAL RESULTS"
log "========================================"
if [ $judge_ok -eq 0 ]; then
    log "ContractJudge:  ✅ $judge_addr"
else
    log "ContractJudge:  ❌ DEPLOY FAILED"
fi
if [ $minimal_ok -eq 0 ]; then
    log "MinimalCounter: ✅ $minimal_addr"
else
    log "MinimalCounter: ❌ DEPLOY FAILED"
fi

# Save addresses for frontend
echo "{\"judge_address\":\"$judge_addr\",\"minimal_address\":\"$minimal_addr\",\"deployed_at\":\"$(date -u '+%Y-%m-%dT%H:%M:%SZ')\"}" > /home/administrator/contract-judge/deployed_addresses.json
log ""
log "Addresses saved to deployed_addresses.json"
cat /home/administrator/contract-judge/deployed_addresses.json
