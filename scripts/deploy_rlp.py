#!/usr/bin/env python3.14
"""Deploy to GenLayer Studio Net with proper RLP encoding."""
import sys, json, time

sys.path.insert(0, '/home/administrator/.local/lib/python3.14/site-packages')

RPC = 'https://studio.genlayer.com/api'
PRIVATE_KEY = '0x023d076ab40ea46c59ac7ca7cecfaa2db5fa10b7a481aef27cf68e9cc5a8c0af'
CHAIN_ID = 421614
CONSENSUS = '0xb7278A61aa25c888815aFC32Ad3cC52fF24fE575'

from eth_account import Account
from web3 import Web3, HTTPProvider

acct = Account.from_key(PRIVATE_KEY)
w3 = Web3(HTTPProvider(RPC))

with open('/home/administrator/contract-judge/contracts/judge_contract.py') as f:
    code = f.read()

# GenLayer deploy format: RLP([code, calldata, leaderOnly])
# code = contract source string
# calldata = empty bytes for no constructor args (using makeCalldataObject format)
# leaderOnly = False (0)

# Use RLP encoding like genlayer-js does
import rlp

# Empty calldata (void 0, [], {} -> empty)
calldata = b''  # empty

# Build the payload: [code, calldata, leaderOnly]
payload = [code.encode('utf-8'), calldata, False]
serialized = rlp.encode(payload)
print(f'Payload length: {len(serialized)}')

nonce = w3.eth.get_transaction_count(acct.address)
gas_price = w3.eth.gas_price

tx = {
    'nonce': nonce,
    'to': CONSENSUS,
    'data': serialized.hex(),
    'gas': 5000000,
    'gasPrice': gas_price,
    'chainId': CHAIN_ID,
    'value': 0,
}

signed = acct.sign_transaction(tx)
tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
print(f'TX: {tx_hash.hex()}')

for i in range(50):
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
