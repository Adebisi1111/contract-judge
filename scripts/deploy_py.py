#!/usr/bin/env python3.14
"""Deploy judge_contract.py to GenLayer Studio Net using eth_account for signing."""
import sys, os, json, time

sys.path.insert(0, '/home/administrator/.local/lib/python3.14/site-packages')

RPC = 'https://studio.genlayer.com/api'
PRIVATE_KEY = '0x023d076ab40ea46c59ac7ca7cecfaa2db5fa10b7a481aef27cf68e9cc5a8c0af'
CHAIN_ID = 421614
CONSENSUS_CONTRACT = '0xb7278A61aa25c888815aFC32Ad3cC52fF24fE575'  # from genlayer-js studionet chain

from eth_account import Account
from web3 import Web3, HTTPProvider

# Derive account
acct = Account.from_key(PRIVATE_KEY)
print(f'Account: {acct.address}')
print(f'Chain ID: {CHAIN_ID}')
print(f'Consensus contract: {CONSENSUS_CONTRACT}')

w3 = Web3(HTTPProvider(RPC))
print(f'Connected: {w3.is_connected()}')

# Read contract code
with open('/home/administrator/contract-judge/contracts/judge_contract.py') as f:
    code = f.read()
print(f'Code length: {len(code)}')

# Encode the deployment data for GenLayer consensus contract
# GenLayer expects: [code, constructorCalldata, leaderOnly] serialized
# For deploy: code=contract source, calldata=empty (no constructor args), leaderOnly=false

# The GenLayer deployment format: serialize([code, calldata, leaderOnly])
# Using RLP-like encoding as GenLayer expects
import rlp
from eth_account.messages import encode_typed_data

# Build the deployment payload as GenLayer expects
# Format: [code_string, calldata_bytes, leaderOnly_bool]
# Serialized via GenLayer's custom encoder

# For now, use the simpler approach: send to consensus contract with encoded data
# The data format is: len(code) + code + len(calldata) + calldata + leaderOnly

# Actually, let's check what genlayer-js does by looking at the _encodeAddTransactionData
# It encodes [code, makeCalldataObject(...), leaderOnly] using a custom serializer

# Simplest approach: use the same format as the working deployment
# The working tx had calldata "Bg==" (base64 for "{}") and contract_code field
# This suggests the deployment data is structured differently than a simple call

# Let's try encoding as GenLayer expects: JSON.stringify the params and send
deploy_data = json.dumps({
    'code': code,
    'args': [],
    'leaderOnly': False
})

# Build transaction
nonce = w3.eth.get_transaction_count(acct.address)
gas_price = w3.eth.gas_price

# Estimate gas (use generous limit)
gas_limit = 5000000

tx = {
    'nonce': nonce,
    'to': CONSENSUS_CONTRACT,
    'data': deploy_data,  # This might not be the right format
    'gas': gas_limit,
    'gasPrice': gas_price,
    'chainId': CHAIN_ID,
    'value': 0,
}

signed = acct.sign_transaction(tx)
print(f'TX hash: {signed.hash.hex()}')

# Send raw transaction
tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
print(f'Sent TX: {tx_hash.hex()}')

# Wait for receipt
for i in range(30):
    time.sleep(3)
    try:
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        if receipt:
            status = 'ACCEPTED' if receipt.status == 1 else 'REJECTED'
            print(f'Check {i+1}: status={status}, gasUsed={receipt.gasUsed}, contractAddress={receipt.contractAddress}')
            if receipt.contractAddress:
                print(f'\nDEPLOYED: {receipt.contractAddress}')
                break
    except Exception as e:
        print(f'  Check {i+1}: {e}')
else:
    print('\nTimed out waiting for receipt')
