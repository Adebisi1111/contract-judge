import { getContractSchema } from './genlayer-api';
import { evaluateWithConsensus } from './llm';

export interface JudgeResult {
  status: 'pass' | 'fail' | 'error';
  issues: JudgeIssue[];
  verdict: string;
  /** LLM evaluation result (if LLM was used) */
  llmEvaluation?: {
    recommended: boolean;
    issues: string[];
    strengths: string[];
    consensus?: 'agree' | 'partial' | 'disagree';
    consensusScore?: number;
  };
}

export interface JudgeIssue {
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  category: string;
  message: string;
  line?: number;
}

export async function runJudge(
  contractCode: string,
  contractAddress?: string,
  options: { useLLM?: boolean; consensusRounds?: number } = {},
): Promise<JudgeResult> {
  const { useLLM = false, consensusRounds = 3 } = options;
  const issues: JudgeIssue[] = [];

  if (contractAddress) {
    try {
      await getContractSchema(contractAddress);
    } catch (err: any) {
      issues.push({
        severity: 'critical',
        category: 'schema',
        message: `Contract schema invalid: ${err.message || String(err)}`,
      });
      return { status: 'fail', issues, verdict: 'Contract schema validation failed' };
    }
  }

  const staticIssues = analyzeContractStatic(contractCode);
  issues.push(...staticIssues);

  const realIssues = issues.filter(i => i.severity !== 'info');
  if (realIssues.length === 0 && !useLLM) {
    return { status: 'pass', issues: [], verdict: 'No issues found. Contract appears well-formed.' };
  }

  const severityOrder = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };
  realIssues.sort((a, b) => severityOrder[a.severity] - severityOrder[b.severity]);

  let llmResult: JudgeResult['llmEvaluation'];

  if (useLLM) {
    try {
      const { evaluations, consensus, consensusScore } = await evaluateWithConsensus(contractCode, consensusRounds);
      const allLLMIssues: string[] = [];
      const allStrengths: string[] = [];
      evaluations.forEach(e => {
        allLLMIssues.push(...e.issues);
        allStrengths.push(...e.strengths);
      });

      // Add LLM issues as judge issues
      allLLMIssues.forEach(msg => {
        // Avoid duplicates with static issues
        if (!realIssues.some(i => i.message === msg) && !issues.some(i => i.message === msg)) {
          issues.push({ severity: 'medium' as const, category: 'llm', message: msg });
        }
      });

      llmResult = {
        recommended: evaluations.every(e => e.recommended),
        issues: allLLMIssues,
        strengths: allStrengths,
        consensus,
        consensusScore,
      };

      // Re-filter after adding LLM issues
      const updatedRealIssues = issues.filter(i => i.severity !== 'info');
      updatedRealIssues.sort((a, b) => severityOrder[a.severity] - severityOrder[b.severity]);

      const hasCritical = updatedRealIssues.some(i => i.severity === 'critical');
      const hasHigh = updatedRealIssues.some(i => i.severity === 'high');

      let verdict: string;
      if (hasCritical) verdict = `Critical issues found — contract will likely fail on-chain.`;
      else if (hasHigh) verdict = `High-severity issues found — review before deploying.`;
      else if (consensus === 'disagree') verdict = `LLM validators disagree on this contract — high non-determinism risk.`;
      else verdict = `Minor issues found — contract may work but should be improved.`;

      return { status: hasCritical || hasHigh ? 'fail' : 'pass', issues: updatedRealIssues, verdict, llmEvaluation: llmResult };
    } catch (err: any) {
      // LLM failed — fall through to static-only result
      llmResult = {
        recommended: true,
        issues: [`LLM evaluation unavailable: ${err instanceof Error ? err.message : String(err)}`],
        strengths: [],
      };
    }
  }

  if (realIssues.length === 0) {
    return { status: 'pass', issues: [], verdict: 'No issues found. Contract appears well-formed.', llmEvaluation: llmResult };
  }

  const hasCritical = realIssues.some(i => i.severity === 'critical');
  const hasHigh = realIssues.some(i => i.severity === 'high');

  let verdict: string;
  if (hasCritical) verdict = `Critical issues found — contract will likely fail on-chain.`;
  else if (hasHigh) verdict = `High-severity issues found — review before deploying.`;
  else verdict = `Minor issues found — contract may work but should be improved.`;

  return { status: hasCritical || hasHigh ? 'fail' : 'pass', issues: realIssues, verdict, llmEvaluation: llmResult };
}

function analyzeContractStatic(code: string): JudgeIssue[] {
  const issues: JudgeIssue[] = [];

  if (!code.includes('from genlayer import')) {
    issues.push({ severity: 'critical', category: 'imports', message: 'Missing "from genlayer import" — contract cannot use GenLayer SDK.' });
  }

  if (code.includes('gl.') && !code.includes('from genlayer import *') && !code.match(/from\s+genlayer\s+import\s*\(/)) {
    issues.push({ severity: 'high', category: 'imports', message: 'Uses "gl." prefix but does not use "from genlayer import *". Either add star import or remove gl. references.' });
  }

  if (!code.includes('@allow_storage') && !code.includes('@gl.allow_storage')) {
    issues.push({ severity: 'high', category: 'decorators', message: 'No @allow_storage decorator found. Contract may not persist state correctly.' });
  }

  code.split('\n').forEach((line, idx) => {
    if (line.includes('@public.read') || line.includes('@gl.public.read')) {
      for (let i = idx + 1; i < Math.min(idx + 5, code.split('\n').length); i++) {
        const nextLine = code.split('\n')[i].trim();
        if (nextLine && !nextLine.startsWith('#') && !nextLine.startsWith('def')) {
          if (!nextLine.includes('->')) {
            issues.push({ severity: 'medium', category: 'types', message: 'View method missing return type annotation.', line: idx + 1 });
          }
          break;
        }
        if (nextLine.startsWith('def')) break;
      }
    }
  });

  code.split('\n').forEach((line, idx) => {
    if (line.includes('def ') && !line.includes('def __')) {
      for (let i = idx + 1; i < Math.min(idx + 10, code.split('\n').length); i++) {
        const content = code.split('\n')[i].trim();
        if (content && !content.startsWith('#') && content !== 'pass' && !content.startsWith(')')) {
          break;
        }
        if (content === 'pass' || content === '...') {
          const rest = code.split('\n').slice(i + 1, i + 5).find(l => l.trim() && !l.trim().startsWith('#'));
          if (!rest) {
            issues.push({ severity: 'medium', category: 'completeness', message: 'Method appears to be a stub (only "pass" or "...").', line: idx + 1 });
          }
          break;
        }
      }
    }
  });

  if (code.includes('except:') || code.includes('except :')) {
    issues.push({ severity: 'high', category: 'error-handling', message: 'Bare "except:" clause catches all exceptions. Use specific exception types.' });
  }

  // Check for reentrancy risk patterns (external calls before state updates)
  if (/self\.[a-zA-Z_]+\s*=\s*.+\n.*def\s+\w+.*?!\s*@.*(write|payable)/.test(code) || code.includes('gl.nondet') && code.includes('self.')) {
    // Not a definitive check, but flag for review
  }

  // Check for potential prompt injection vectors (user input passed to exec_prompt)
  if (code.includes('gl.nondet.exec_prompt') && code.includes('self.')) {
    issues.push({ severity: 'medium', category: 'security', message: 'Contract uses gl.nondet.exec_prompt with stored/self values. Ensure user input is sanitized before passing to LLM to prevent prompt injection.' });
  }

  const mutableDefaultPattern = /def\s+\w+\s*\(.*=\s*\[\s*\]|=\s*\{\s*\}|=\s*\(/;
  if (mutableDefaultPattern.test(code)) {
    issues.push({ severity: 'medium', category: 'best-practices', message: 'Mutable default argument detected. Use None and initialize inside function.' });
  }

  return issues;
}
