// GenLayer Bradbury Testnet — RPC client with write support
// Uses direct JSON-RPC for reads and wallet eth_sendTransaction for writes.

const GENLAYER_RPC = 'https://rpc-bradbury.genlayer.com';

export interface GenLayerChain {
  id: number;
  name: string;
  nativeCurrency: { name: string; symbol: string; decimals: number };
  rpcUrls: { default: { http: string[]; webSocket: string[] } };
  blockExplorers: { default: { name: string; url: string } };
}

export const GENLAYER_CHAIN: GenLayerChain = {
  id: 4221,
  name: 'GenLayer Bradbury Testnet',
  nativeCurrency: { name: 'GEN', symbol: 'GEN', decimals: 18 },
  rpcUrls: { default: { http: [GENLAYER_RPC], webSocket: [] } },
  blockExplorers: { default: { name: 'Bradbury Explorer', url: 'https://explorer-bradbury.genlayer.com' } },
};

/**
 * Call a GenLayer JSON-RPC method directly.
 */
async function rpcCall(method: string, params: unknown[] = []): Promise<unknown> {
  const res = await fetch(GENLAYER_RPC, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method, params }),
  });
  const data = await res.json();
  if (data.error) throw new Error(String(data.error.message || data.error));
  return data.result;
}

// ---------------------------------------------------------------------------
// Read methods (gen_call)
// ---------------------------------------------------------------------------

export async function getContractSchema(contractAddress: string): Promise<unknown> {
  return rpcCall('gen_getContractSchema', [contractAddress]);
}

export async function getContractCode(contractAddress: string): Promise<string> {
  return rpcCall('gen_getContractCode', [contractAddress]) as Promise<string>;
}

export async function genCall(
  contractAddress: string,
  methodName: string,
  args: (string | number | null | undefined)[] = [],
): Promise<unknown> {
  return rpcCall('gen_call', [contractAddress, methodName, args]);
}

// ---------------------------------------------------------------------------
// Write methods (eth_sendTransaction via wallet)
// ---------------------------------------------------------------------------

// Function selectors (keccak256 first 4 bytes)
const SELECTORS: Record<string, string> = {
  submit_contract: '0x', // will be set after deployment
  analyze: '0x',
};

export function setSelectors(selectors: Record<string, string>) {
  Object.assign(SELECTORS, selectors);
}

// GenLayer calldata encoding: ULEB128-prefixed strings in a tagged map
function encodeULEB128(value: number): number[] {
  const bytes: number[] = [];
  do {
    let byte = value & 0x7f;
    value >>>= 7;
    if (value !== 0) byte |= 0x80;
    bytes.push(byte);
  } while (value !== 0);
  return bytes;
}

function encodeGenLayerString(str: string): number[] {
  const encoded = new TextEncoder().encode(str);
  return [...encodeULEB128(encoded.length), ...encoded];
}

function encodeGenLayerArray(items: (string | null | undefined)[]): number[] {
  const result = [...encodeULEB128(items.length)];
  for (const item of items) {
    if (item != null) {
      result.push(...encodeGenLayerString(item));
    }
  }
  return result;
}

function encodeGenLayerCalldata(method: string, args: (string | null | undefined)[]): number[] {
  // Format: 0x06 (map tag) + "method" key + method value + "args" key + args array
  const result = [0x06];
  result.push(...encodeGenLayerString("method"));
  result.push(...encodeGenLayerString(method));
  result.push(...encodeGenLayerString("args"));
  result.push(...encodeGenLayerArray(args));
  return result;
}

export function encodeCalldata(method: string, args: (string | null | undefined)[]): string {
  return '0x' + encodeGenLayerCalldata(method, args).map(b => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Send a write transaction via the connected wallet.
 * Uses wallet's eth_sendTransaction (MetaMask signs locally, then sends).
 */
export async function sendWriteTx(
  wallet: string,
  contractAddress: string,
  method: string,
  args: (string | null | undefined)[],
): Promise<string> {
  const data = encodeCalldata(method, args);

  if (!window.ethereum) throw new Error('No wallet found');

  const hash = await window.ethereum.request({
    method: 'eth_sendTransaction',
    params: [{
      from: wallet,
      to: contractAddress,
      data,
    }],
  });
  return hash as string;
}

/**
 * Wait for a transaction receipt.
 * Polls eth_getTransactionReceipt until it appears.
 */
export async function waitForReceipt(
  txHash: string,
  maxWaitMs = 300000,
  pollIntervalMs = 5000,
): Promise<{ status: string; contractAddress?: string } | null> {
  const start = Date.now();
  while (Date.now() - start < maxWaitMs) {
    try {
      const receipt = await rpcCall('eth_getTransactionReceipt', [txHash]);
      if (receipt) {
        return receipt as { status: string; contractAddress?: string };
      }
    } catch {
      // keep polling
    }
    await new Promise(r => setTimeout(r, pollIntervalMs));
  }
  return null;
}

/**
 * Connect wallet and switch to GenLayer Bradbury Testnet.
 */
export async function connectWallet(): Promise<string> {
  if (!window.ethereum) throw new Error('No wallet found');

  try {
    await window.ethereum.request({
      method: 'wallet_switchEthereumChain',
      params: [{ chainId: '0x107d' }], // 4221
    });
  } catch {
    await window.ethereum.request({
      method: 'wallet_addEthereumChain',
      params: [{
        chainId: '0x107d',
        chainName: 'GenLayer Bradbury Testnet',
        nativeCurrency: { name: 'GEN', symbol: 'GEN', decimals: 18 },
        rpcUrls: [GENLAYER_RPC],
        blockExplorerUrls: ['https://explorer-bradbury.genlayer.com'],
      }],
    });
  }

  const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
  return accounts[0];
}
