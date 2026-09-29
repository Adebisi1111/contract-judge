// GenLayer Studio Net — custom RPC client
// Uses viem's http transport under the hood but calls GenLayer-specific JSON-RPC methods.

const GENLAYER_RPC = 'https://studio.genlayer.com/api';

export interface GenLayerChain {
  id: number;
  name: string;
  nativeCurrency: { name: string; symbol: string; decimals: number };
  rpcUrls: { default: { http: string[]; webSocket: string[] } };
  blockExplorers: { default: { name: string; url: string } };
}

export const GENLAYER_CHAIN: GenLayerChain = {
  id: 421614,
  name: 'GenLayer Studio Net',
  nativeCurrency: { name: 'GEN', symbol: 'GEN', decimals: 18 },
  rpcUrls: { default: { http: [GENLAYER_RPC], webSocket: [] } },
  blockExplorers: { default: { name: 'GenLayer Explorer', url: 'https://explorer-studio.genlayer.com' } },
};

/**
 * Call a GenLayer JSON-RPC method directly.
 * Bypasses viem's typed method set since GenLayer uses custom methods.
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

export async function getContractSchema(contractAddress: string): Promise<unknown> {
  return rpcCall('gen_getContractSchema', [contractAddress]);
}

export async function getContractCode(contractAddress: string): Promise<string> {
  return rpcCall('gen_getContractCode', [contractAddress]) as Promise<string>;
}

export async function getContractState(contractAddress: string): Promise<unknown> {
  return rpcCall('gen_getContractState', [contractAddress]);
}

export async function genCall(
  contractAddress: string,
  methodName: string,
  args: (bigint | string | number | null | undefined)[] = [],
): Promise<unknown> {
  return rpcCall('gen_call', [contractAddress, methodName, args]);
}


