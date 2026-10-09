import { getClient, BRADBURY_FEE } from './genlayer-api';

export interface JudgeResult {
  status: 'pass' | 'fail' | 'error';
  issues: JudgeIssue[];
  verdict: string;
  onChain?: {
    submissionId: string;
    txHash: string;
    severity: string;
    issues: string[];
    strengths: string[];
    recommended: boolean;
    analyzer: string;
    explorerUrl: string;
  };
}

export interface JudgeIssue {
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  category: string;
  message: string;
  line?: number;
}

const EXPLORER = 'https://explorer-bradbury.genlayer.com';

/** Progress callback: lets the UI show what's happening instead of a dead spinner. */
export type JudgeProgress = (
  phase: 'submitting' | 'analyzing' | 'finalizing',
  detail: string,
) => void;

const ANALYZE_ROUNDS = 12;          // ride out a slow-consensus window
const VERDICT_POLLS = 45;           // ~3 min of background recovery polling
const VERDICT_POLL_MS = 4000;

/** Extract a consensus result name from a receipt (SDK puts it top-level). */
function receiptResult(r: any): string {
  return r?.resultName || r?.consensusData?.resultName || '';
}

/** Read the decoded verdict for a submission id, or null if not yet committed. */
async function readVerdict(client: any, contractAddress: string, submissionId: string) {
  const verdict = await client.readContract({
    address: contractAddress, functionName: 'get_verdict', args: [submissionId],
  });
  if (verdict && verdict.exists && verdict.result) return verdict;
  return null;
}

/**
 * On-chain judge. Submits code to the ContractJudge contract, runs the LLM
 * consensus analysis, and reads the decoded verdict — all via genlayer-js.
 *
 * `analyze` is a non-deterministic LLM consensus round: any single attempt can
 * return NO_MAJORITY / TIMEOUT before one reaches AGREE. We therefore (a) retry
 * generously, and (b) keep polling get_verdict afterward so a verdict that
 * commits slightly after we stop driving it is still surfaced — the submission
 * is never orphaned.
 */
export async function runJudge(
  contractCode: string,
  wallet: string,
  contractAddress: string,
  onProgress?: JudgeProgress,
): Promise<JudgeResult> {
  if (!wallet) throw new Error('Connect wallet first');
  if (!contractAddress) throw new Error('Contract address required');
  if (!contractCode.trim()) throw new Error('Contract code is empty');

  // Account (address string) + provider are bound in getClient(); the SDK
  // routes signing to the injected wallet because account is an address string.
  const client = getClient(wallet as `0x${string}`) as any;
  const fees = { feeValue: BRADBURY_FEE };

  // 1) submit_contract (write)
  onProgress?.('submitting', 'Submitting contract on-chain…');
  const submitHash = await client.writeContract({
    address: contractAddress,
    functionName: 'submit_contract',
    args: [contractCode],
    value: 0n,
    fees,
  });
  await client.waitForTransactionReceipt({ hash: submitHash, waitUntil: 'finalized', retries: 240 });

  // 2) read the submission id from decoded contract state
  const stats = await client.readContract({
    address: contractAddress, functionName: 'get_stats', args: [],
  });
  const total = Number(stats.total_submissions ?? stats[0] ?? 0);
  const submissionId = String(total - 1);

  // 3) analyze (write — triggers LLM consensus), retry on non-committing rounds
  let analyzeHash = '';
  let agreed = false;
  for (let attempt = 1; attempt <= ANALYZE_ROUNDS && !agreed; attempt++) {
    onProgress?.('analyzing', `AI validators reaching consensus — round ${attempt} of ${ANALYZE_ROUNDS}…`);
    const h = await client.writeContract({
      address: contractAddress,
      functionName: 'analyze',
      args: [submissionId],
      value: 0n,
      fees,
    });
    analyzeHash = h;
    const r = await client.waitForTransactionReceipt({ hash: h, waitUntil: 'finalized', retries: 240 });
    if (receiptResult(r) === 'AGREE') {
      agreed = true;
    } else if (attempt < ANALYZE_ROUNDS) {
      await new Promise(res => setTimeout(res, 5000));
    }
  }

  // 4) get_verdict (decoded read). Even if our own rounds didn't agree, a verdict
  //    may still commit — poll it so a late consensus is surfaced, never orphaned.
  onProgress?.('finalizing', agreed ? 'Reading verdict…' : 'Consensus is slow — waiting for the verdict to commit…');
  let verdict: any = null;
  for (let i = 0; i < VERDICT_POLLS; i++) {
    verdict = await readVerdict(client, contractAddress, submissionId);
    if (verdict) break;
    await new Promise(res => setTimeout(res, VERDICT_POLL_MS));
  }

  if (!verdict) {
    throw new Error(
      'Consensus is unusually slow right now and the verdict has not committed yet. ' +
      'Your submission is saved on-chain — open this page again in a few minutes and ' +
      'the verdict will be waiting.'
    );
  }

  const r = verdict.result;
  const severity = (r.severity || 'none').toLowerCase();
  const blocking = severity === 'critical' || severity === 'high';

  return {
    status: blocking ? 'fail' : 'pass',
    issues: (r.issues || []).map((msg: string) => ({
      severity: (['critical', 'high', 'medium', 'low'].includes(severity) ? severity : 'info') as JudgeIssue['severity'],
      category: 'on-chain',
      message: msg,
    })),
    verdict: blocking
      ? `${severity === 'critical' ? 'Critical' : 'High'}-severity issues found — review before deploying.`
      : 'No blocking issues. Contract appears well-formed.',
    onChain: {
      submissionId,
      txHash: analyzeHash,
      severity: r.severity,
      issues: r.issues || [],
      strengths: r.strengths || [],
      recommended: r.recommended,
      analyzer: r.analyzer || '',
      explorerUrl: `${EXPLORER}/address/${contractAddress}`,
    },
  };
}

/**
 * Local static preview shown BEFORE submitting on-chain. This is NOT the
 * verdict — the authoritative verdict comes from on-chain LLM consensus.
 */
export function analyzeStatic(code: string): JudgeIssue[] {
  const issues: JudgeIssue[] = [];
  if (!code.includes('from genlayer import')) {
    issues.push({ severity: 'critical', category: 'imports', message: 'Missing "from genlayer import".' });
  }
  if (!code.includes('@allow_storage') && !code.includes('@gl.allow_storage')) {
    issues.push({ severity: 'high', category: 'decorators', message: 'No @allow_storage decorator found.' });
  }
  if (code.includes('except:') || code.includes('except :')) {
    issues.push({ severity: 'high', category: 'error-handling', message: 'Bare "except:" clause.' });
  }
  if (code.includes('@staticmethod')) {
    issues.push({ severity: 'critical', category: 'genvm', message: '@staticmethod is rejected by GenVM.' });
  }
  return issues;
}
