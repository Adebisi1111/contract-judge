import { createClient, chains } from 'genlayer-js';
import { readFileSync } from 'fs';
import { privateKeyToAccount } from 'viem/accounts';

const PRIVATE_KEY = '0x023d90e2fc56bb73bf201156528084f9c8e5eb8c98f45b8ebe2b0ddce2d8b2fce5';

const account = privateKeyToAccount(PRIVATE_KEY);
console.log('Account:', account.address);

const client = createClient({
  chain: chains.studionet,
  account,
});

console.log('Chain:', client.chain.name);
console.log('Consensus main contract:', client.chain.consensusMainContract?.address);

const code = readFileSync('contracts/judge_contract.py', 'utf8');
console.log('Code length:', code.length);

console.log('\nDeploying...');
const txHash = await client.deployContract({ code, leaderOnly: false });
console.log('EVM TX hash:', txHash);

for (let i = 0; i < 50; i++) {
  await new Promise(r => setTimeout(r, 3000));
  try {
    const receipt = await client.getTransactionReceipt({ hash: txHash });
    const status = receipt.status_name;
    const contractAddr = receipt.contractAddress;
    const blockNum = receipt.blockNumber;
    console.log(`Check ${i+1}: status=${status}, contract=${contractAddr}, block=${blockNum}`);
    if (contractAddr) {
      console.log('\n✓ DEPLOYED');
      console.log('Contract:', contractAddr);
      console.log('TX:', txHash);
      break;
    }
    if (status === 'REJECTED' || status === 'FAILED') {
      console.log('\n✗ REJECTED');
      break;
    }
  } catch (e) {
    console.log(`  Check ${i+1}: ${e.message?.slice(0,150) || e}`);
  }
}
