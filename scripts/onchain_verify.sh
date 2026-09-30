#!/bin/bash
# Deploy both contracts and verify on-chain
PASSWORD="test1234"
GPS="/home/administrator/.local/bin/genlayer"
RPC="https://studio.genlayer.com/api"

deploy_and_check() {
    local contract="$1"
    local label="$2"
    echo ""
    echo "========================================"
    echo "Deploying $label: $contract"
    echo "========================================"
    
    # Deploy
    output=$(echo "$PASSWORD" | $GPS deploy --rpc "$RPC" --contract "$contract" 2>&1)
    echo "$output"
    
    # Extract contract address from deploy output
    addr=$(echo "$output" | grep "Contract Address:" | tail -1 | sed 's/.*Contract Address: '\''//;s/'\''.*//')
    tx=$(echo "$output" | grep "Transaction Hash:" | tail -1 | sed 's/.*Transaction Hash: '\''//;s/'\''.*//')
    
    echo ""
    echo "Contract Address: $addr"
    echo "Transaction Hash: $tx"
    
    if [ -z "$addr" ] || [ "$addr" = "" ]; then
        echo "ERROR: Could not extract contract address"
        return 1
    fi
    
    # Wait for on-chain (poll up to 90s)
    echo "Waiting for on-chain confirmation..."
    for i in $(seq 1 18); do
        code=$(curl -s -X POST "$RPC" \
            -H "Content-Type: application/json" \
            -d "{\"jsonrpc\":\"2.0\",\"method\":\"gen_getContractCode\",\"params\":[\"$addr\"],\"id\":1}" 2>&1 | \
            python3.14 -c "import sys,json; d=json.load(sys.stdin); print(d.get('result',''))" 2>/dev/null)
        
        if [ -n "$code" ]; then
            size=$(echo -n "$code" | wc -c)
            echo "ON-CHAIN confirmed after ~$((i*5))s — $size bytes"
            echo "First 150 chars: $(echo "$code" | head -c 150)"
            return 0
        fi
        sleep 5
    done
    
    echo "NOT FOUND after 90s polling"
    return 1
}

deploy_and_check "contracts/judge_contract.py" "ContractJudge"
deploy_and_check "contracts/minimal.py" "MinimalCounter"

echo ""
echo "========================================"
echo "DONE"
echo "========================================"
