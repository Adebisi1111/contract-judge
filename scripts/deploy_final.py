#!/usr/bin/env python3.14
"""Deploy judge_contract.py to GenLayer Studio Net."""
import sys, os, json, time

sys.path.insert(0, '/home/administrator/.local/lib/python3.14/site-packages')

RPC = 'https://studio.genlayer.com/api'
PRIVATE_KEY = '0x023d076ab40ea46c59ac7ca7cecfaa2db5fa10b7a481aef27cf68e9cc5a8c0af'
CHAIN_ID = 421614

from eth_account import Account
from web3 import Web3, HTTPProvider

acct = Account.from_key(PRIVATE_KEY)
print(f'Account: {acct.address}')

w3 = Web3(HTTPProvider(RPC))
print(f'Connected: {w3.is_connected()}')
print(f'Chain ID: {w3.eth.chain_id}')

with open('/home/administrator/contract-judge/contracts/judge_contract.py') as f:
    code = f.read()
print(f'Code: {len(code)} chars')

# GenLayer deploy: POST to RPC with jsonrpc method gen_deployContract
# Or send signed tx to consensus contract

# Try the gen_deployContract RPC method first (simpler)
payload = {
    'jsonrpc': '2.0',
    'id': 1,
    'method': 'gen_deployContract',
    'params': [code, []]  # code, args
}

print('\nAttempting RPC deploy...')
try:
    resp = w3.manager.request_blocking(payload['method'], payload['params'])
    print('RPC response:', resp)
except Exception as e:
    print(f'RPC deploy failed: {e}')

# Fallback: send signed transaction to consensus contract
print('\nAttempting signed tx deploy...')
CONSENSUS = '0xb7278A61aa25c888815aFC32Ad3cC52fF24fE575'

# Encode deployment data as GenLayer expects
# The data format: rlp-encoded [code, calldata, leaderOnly]
# But simpler: send as a call to the consensus contract with the code in calldata

# Actually, let's look at what the genlayer-js deployContract does:
# It calls _sendTransaction which sends to consensusMainContract with encoded data
# The encoded data is: encodeAddTransactionData(client, sender, recipient, data, rotations)
# Which produces the calldata for the consensus contract

# For a direct approach, let's try eth_sendTransaction via RPC (if supported)
# Or sign and send raw

nonce = w3.eth.get_transaction_count(acct.address)
gas_price = w3.eth.gas_price

# Try with a simple data payload first - the code as calldata
tx = {
    'nonce': nonce,
    'to': CONSENSUS,
    'data': code.encode('utf-8'),
    'gas': 5000000,
    'gasPrice': gas_price,
    'chainId': CHAIN_ID,
    'value': 0,
}

signed = acct.sign_transaction(tx)
tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
print(f'Sent TX: {tx_hash.hex()}')

for i in range(40):
    time.sleep(3)
    try:
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        if receipt:
            status = 'ACCEPTED' if receipt['status'] == 1 else 'REJECTED'
            gas_used = receipt['gasUsed']
            contract_addr = receipt.get('contractAddress')
            print(f'Check {i+1}: status={status}, gas={gas_used}, contract={contract_addr}')
            if contract_addr:
                print(f'\nDEPLOYED: {contract_addr}')
                print(f'TX: {tx_hash.hex()}')
                break
    except Exception as e:
        print(f'  Check {i+1}: {e}')
else:
    print('\nTimed out')
