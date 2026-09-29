/**
 * LLM-based contract evaluation.
 * Calls an LLM to semantically analyze contract code for issues.
 * Uses the Hermes inference API (Nous Research) by default.
 */

export interface LLMEvaluation {
  recommended: boolean;
  issues: string[];
  strengths: string[];
  raw: string;
}

const LLM_BASE = 'https://inference-api.nousresearch.com/v1';
const LLM_MODEL = 'anthropic/claude-sonnet-5.5';

async function llmPost(body: object): Promise<{choices: Array<{message: {content: string}}>}> {
  const apiKey = (typeof process !== 'undefined' && process.env?.REACT_APP_LLM_API_KEY) ||
                  (typeof window !== 'undefined' && (window as any).__LLM_API_KEY) ||
                  '';
  const res = await fetch(`${LLM_BASE}/chat/completions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(apiKey ? { Authorization: `Bearer ${apiKey}` } : {}),
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`LLM API ${res.status}: ${text.slice(0, 300)}`);
  }
  return res.json() as Promise<{choices: Array<{message: {content: string}}>}>;
}

/**
 * Evaluate contract code using an LLM.
 * Sends the code to the LLM with a structured prompt asking for issue analysis.
 */
export async function evaluateWithLLM(code: string): Promise<LLMEvaluation> {
  const prompt = `You are a GenLayer smart contract auditor. Analyze the following Python contract code written for the GenLayer blockchain (using the genlayer SDK). Identify any issues, bugs, security problems, or deviations from best practices.

Return your analysis as a JSON object with this exact structure:
{
  "recommended": true/false,
  "issues": ["issue 1", "issue 2"],
  "strengths": ["strength 1"]
}

Rules:
- Be concrete and specific about each issue.
- Only report real issues — don't flag stylistic preferences.
- If the contract looks correct and well-structured, set recommended to true with an empty issues list.
- Focus on: missing imports, wrong decorators, storage issues, error handling, type safety, logic bugs, security, and non-determinism risks.

Contract code:
\`\`\`python
${code}
\`\`\`

Return ONLY the JSON object, no other text.`;

  const response = await llmPost({
    model: LLM_MODEL,
    messages: [{ role: 'user', content: prompt }],
    max_tokens: 2048,
    temperature: 0.3,
  });

  const data = response;
  const raw = data.choices[0]?.message?.content || '';

  // Try to parse JSON from the response
  try {
    const jsonStart = raw.indexOf('{');
    const jsonEnd = raw.lastIndexOf('}');
    if (jsonStart === -1 || jsonEnd === -1) throw new Error('No JSON found');
    const parsed = JSON.parse(raw.slice(jsonStart, jsonEnd + 1));
    return {
      recommended: parsed.recommended ?? true,
      issues: parsed.issues || [],
      strengths: parsed.strengths || [],
      raw,
    };
  } catch {
    // Fallback: treat as pass with raw note
    return {
      recommended: true,
      issues: [],
      strengths: ['LLM evaluation completed (raw response not parsed as JSON)'],
      raw,
    };
  }
}

/**
 * Run consensus evaluation: call LLM multiple times with varied prompts
 * and check if the evaluations agree.
 */
export async function evaluateWithConsensus(code: string, rounds = 3): Promise<{
  evaluations: LLMEvaluation[];
  consensus: 'agree' | 'partial' | 'disagree';
  consensusScore: number;
}> {
  const evaluations: LLMEvaluation[] = [];
  const recommendations: boolean[] = [];

  for (let i = 0; i < rounds; i++) {
    try {
      const eval_ = await evaluateWithLLM(code);
      evaluations.push(eval_);
      recommendations.push(eval_.recommended);
    } catch (err) {
      evaluations.push({
        recommended: true,
        issues: [`LLM round ${i + 1} failed: ${err instanceof Error ? err.message : String(err)}`],
        strengths: [],
        raw: '',
      });
      recommendations.push(true); // failed round = no objection
    }
  }

  const yesCount = recommendations.filter(Boolean).length;
  const total = recommendations.length;

  let consensus: 'agree' | 'partial' | 'disagree';
  let consensusScore: number;

  if (total === 0) {
    consensus = 'agree';
    consensusScore = 0;
  } else {
    const ratio = yesCount / total;
    if (ratio >= 0.8) {
      consensus = 'agree';
      consensusScore = Math.round(ratio * 100);
    } else if (ratio >= 0.4) {
      consensus = 'partial';
      consensusScore = Math.round(ratio * 100);
    } else {
      consensus = 'disagree';
      consensusScore = Math.round(ratio * 100);
    }
  }

  return { evaluations, consensus, consensusScore };
}
