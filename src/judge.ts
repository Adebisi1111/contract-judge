import { genCall, sendWriteTx, waitForReceipt } from './genlayer-api';

export interface JudgeResult {
  status: 'pass' | 'fail' | 'error';
  issues: JudgeIssue[];
  verdict: string;
  /** On-chain submission info */
  onChain?: {
    submissionId: string;
    txHash: string;
    severity: string;
    issues: string[];
    strengths: string[];
    recommended: boolean;
    analyzer: string;
  };
  /** Local static analysis (fallback / preview) */
  staticIssues?: JudgeIssue[];
}

export interface JudgeIssue {
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  category: string;
  message: string;
  line?: number;
}

/**
 * On-chain judge: submits code to the ContractJudge contract and waits for
 * the LLM consensus verdict.
 */
export async function runJudge(
  contractCode: string,
  wallet: string,
  contractAddress: string,
): Promise<JudgeResult> {
  if (!wallet) throw new Error('Connect wallet first');
  if (!contractAddress) throw new Error('Contract address required');
  if (!contractCode.trim()) throw new Error('Contract code is empty');

  // Step 1: submit_contract (write tx)
  const submitTx = await sendWriteTx(wallet, contractAddress, 'submit_contract', [contractCode]);
  await waitForReceipt(submitTx);

  // Step 2: read submission_id from contract state
  const total = await genCall(contractAddress, 'get_stats', []) as { total_submissions: number };
  const submissionId = String(total.total_submissions - 1);

  // Step 3: analyze (write tx — triggers LLM consensus)
  const analyzeTx = await sendWriteTx(wallet, contractAddress, 'analyze', [submissionId]);
  await waitForReceipt(analyzeTx, 300000); // 5 min — LLM consensus takes time

  // Step 4: get_verdict (read)
  const verdictData = await genCall(contractAddress, 'get_verdict', [submissionId]) as {
    exists: boolean;
    result?: {
      severity: string;
      issues: string[];
      strengths: string[];
      recommended: boolean;
      analyzed_at: number;
      analyzer: string;
    };
  };

  if (!verdictData.exists || !verdictData.result) {
    throw new Error('Verdict not found — consensus may have failed');
  }

  const r = verdictData.result;
  const hasCritical = r.severity === 'critical';
  const hasHigh = r.severity === 'high';

  return {
    status: hasCritical || hasHigh ? 'fail' : 'pass',
    issues: r.issues.map(msg => ({ severity: r.severity as JudgeIssue['severity'], category: 'onchain', message: msg })),
    verdict: hasCritical
      ? 'Critical issues found — contract will likely fail on-chain.'
      : hasHigh
        ? 'High-severity issues found — review before deploying.'
        : r.severity === 'medium'
          ? 'Medium issues found — should be improved.'
          : 'No issues found. Contract appears well-formed.',
    onChain: {
      submissionId,
      txHash: analyzeTx,
      severity: r.severity,
      issues: r.issues,
      strengths: r.strengths,
      recommended: r.recommended,
      analyzer: r.analyzer,
    },
  };
}

/**
 * Local static analysis — used as a quick preview before submitting on-chain.
 */
export function analyzeStatic(code: string): JudgeIssue[] {
  const issues: JudgeIssue[] = [];

  if (!code.includes('from genlayer import')) {
    issues.push({ severity: 'critical', category: 'imports', message: 'Missing "from genlayer import" — contract cannot use GenLayer SDK.' });
  }

  if (!code.includes('@allow_storage') && !code.includes('@gl.allow_storage')) {
    issues.push({ severity: 'high', category: 'decorators', message: 'No @allow_storage decorator found.' });
  }

  if (code.includes('except:') || code.includes('except :')) {
    issues.push({ severity: 'high', category: 'error-handling', message: 'Bare "except:" clause catches all exceptions.' });
  }

  if (code.includes('@staticmethod')) {
    issues.push({ severity: 'critical', category: 'genvm', message: '@staticmethod is rejected by GenVM. Use module-level functions instead.' });
  }

  if (/import\s+re\b/.test(code) && !/^import re/m.test(code)) {
    issues.push({ severity: 'critical', category: 'genvm', message: 'Local import re — GenVM rejects local imports. Move to top of file.' });
  }

  if (/:\s*DynArray\[/.test(code) || /:\s*list\[/.test(code)) {
    issues.push({ severity: 'high', category: 'genvm', message: 'Collection type as storage field — GenVM rejects this. Use str and join/split on read.' });
  }

  const mutableDefaultPattern = /def\s+\w+\s*\(.*=\s*\[\s*\]|=\s*\{\s*\}/;
  if (mutableDefaultPattern.test(code)) {
    issues.push({ severity: 'medium', category: 'best-practices', message: 'Mutable default argument detected.' });
  }

  if (code.includes('gl.nondet.exec_prompt') && code.includes('self.')) {
    issues.push({ severity: 'medium', category: 'security', message: 'exec_prompt with stored/self values — ensure user input is sanitized.' });
  }

  return issues;
}
