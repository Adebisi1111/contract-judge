// GenLayer Bradbury Testnet client — built on the OFFICIAL genlayer-js SDK.
// No hand-rolled JSON-RPC transport. Writes go through the connected wallet
// via the SDK client; reads are decoded by the SDK.

import { createClient, chains } from 'genlayer-js';

const CHAIN_ID_HEX = '0x107d'; // 4221

export const GENLAYER_CHAIN = {
  id: 4221,
  name: 'GenLayer Bradbury Testnet',
  nativeCurrency: { name: 'GEN', symbol: 'GEN', decimals: 18 },
  rpcUrls: { default: { http: ['https://rpc-bradbury.genlayer.com'] } },
  blockExplorers: {
    default: { name: 'Bradbury Explorer', url: 'https://explorer-bradbury.genlayer.com' },
  },
};

export const BRADBURY_FEE = '100000000000010352';

let _client: ReturnType<typeof createClient> | null = null;

/**
 * Create (once) and return the SDK client bound to Bradbury and the account.
 */
export function getClient(account: `0x${string}`) {
  if (!_client) {
    _client = createClient({ chain: chains.testnetBradbury, account });
  }
  return _client;
}

/**
 * Connect the wallet, switching/adding the Bradbury chain if needed.
 * Returns the connected account address.
 */
export async function connectWallet(): Promise<string> {
  const eth = (window as any).ethereum;
  if (!eth) throw new Error('No wallet found');

  try {
    await eth.request({
      method: 'wallet_switchEthereumChain',
      params: [{ chainId: CHAIN_ID_HEX }],
    });
  } catch {
    await eth.request({
      method: 'wallet_addEthereumChain',
      params: [
        {
          chainId: CHAIN_ID_HEX,
          chainName: GENLAYER_CHAIN.name,
          nativeCurrency: GENLAYER_CHAIN.nativeCurrency,
          rpcUrls: GENLAYER_CHAIN.rpcUrls.default.http,
          blockExplorerUrls: [GENLAYER_CHAIN.blockExplorers.default.url],
        },
      ],
    });
  }

  const accounts: string[] = await eth.request({ method: 'eth_requestAccounts' });
  return accounts[0];
}
