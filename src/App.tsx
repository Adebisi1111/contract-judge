import { useState, useCallback } from 'react';
import { runJudge, JudgeResult, JudgeIssue } from './judge';

const severityColors: Record<JudgeIssue['severity'], string> = {
  critical: 'bg-red-600/20 text-red-400 border-red-600/40',
  high: 'bg-orange-600/20 text-orange-400 border-orange-600/40',
  medium: 'bg-yellow-600/20 text-yellow-400 border-yellow-600/40',
  low: 'bg-blue-600/20 text-blue-400 border-blue-600/40',
  info: 'bg-gray-600/20 text-gray-400 border-gray-600/40',
};

const severityLabels: Record<JudgeIssue['severity'], string> = {
  critical: 'Critical', high: 'High', medium: 'Medium', low: 'Low', info: 'Info',
};

function IssueChip({ issue }: { issue: JudgeIssue }) {
  return (
    <div className={`flex items-start gap-3 p-3 rounded-lg border ${severityColors[issue.severity]} mb-2`}>
      <div className="flex-shrink-0 mt-0.5"><span className="text-xs font-bold uppercase tracking-wide">{severityLabels[issue.severity]}</span></div>
      <div className="flex-1 min-w-0">
        <p className="text-sm">{issue.message}</p>
        {issue.line && <span className="text-xs opacity-60 mt-1 block">Line {issue.line}</span>}
        <span className="text-xs opacity-40 mt-1 inline-block">{issue.category}</span>
      </div>
    </div>
  );
}

function ResultDisplay({ result }: { result: JudgeResult | null }) {
  if (!result) return null;
  return (
    <div className="mt-6 space-y-4">
      <div className={`rounded-xl border p-5 ${result.status === 'pass' ? 'bg-green-900/20 border-green-700/40' : result.status === 'fail' ? 'bg-red-900/20 border-red-700/40' : 'bg-yellow-900/20 border-yellow-700/40'}`}>
        <div className="flex items-center gap-3 mb-2">
          <span className={`text-2xl ${result.status === 'pass' ? 'text-green-400' : result.status === 'fail' ? 'text-red-400' : 'text-yellow-400'}`}>{result.status === 'pass' ? '✓' : result.status === 'fail' ? '✗' : '!'}</span>
          <div>
            <h2 className="text-lg font-semibold">{result.status === 'pass' ? 'Pass' : result.status === 'fail' ? 'Issues Found' : 'Error'}</h2>
            <p className="text-sm opacity-80">{result.verdict}</p>
          </div>
        </div>
        <div className="mt-3 flex gap-2">
          <span className="px-3 py-1 rounded-full text-xs font-medium bg-gray-800/80 text-gray-300 border border-gray-700/50">{result.issues.length} issue{result.issues.length !== 1 ? 's' : ''}</span>
          {result.status === 'pass' && <span className="px-3 py-1 rounded-full text-xs font-medium bg-green-900/40 text-green-400 border border-green-700/40">Clean</span>}
        </div>
      </div>
      {result.issues.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wide mb-3">Issues</h3>
          <div className="space-y-1">{result.issues.map((issue, i) => <IssueChip key={i} issue={issue} />)}</div>
        </div>
      )}
      {result.llmEvaluation && (
        <div className="mt-6 pt-6 border-t border-gray-800/60">
          <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wide mb-3">LLM Validator Consensus</h3>
          <div className="grid grid-cols-2 gap-3 mb-3">
            <div className={`rounded-lg p-3 border ${result.llmEvaluation?.consensus === 'agree' ? 'bg-green-900/20 border-green-700/40' : result.llmEvaluation?.consensus === 'partial' ? 'bg-yellow-900/20 border-yellow-700/40' : 'bg-red-900/20 border-red-700/40'}`}>
              <div className="text-xs text-gray-500 mb-1">Consensus</div>
              <div className="text-lg font-semibold">{result.llmEvaluation?.consensus?.toUpperCase() ?? '—'}</div>
              {result.llmEvaluation.consensusScore !== undefined && (
                <div className="text-xs text-gray-500 mt-1">{result.llmEvaluation.consensusScore}% agreement</div>
              )}
            </div>
            <div className={`rounded-lg p-3 border ${result.llmEvaluation.recommended ? 'bg-green-900/20 border-green-700/40' : 'bg-red-900/20 border-red-700/40'}`}>
              <div className="text-xs text-gray-500 mb-1">Recommendation</div>
              <div className="text-lg font-semibold">{result.llmEvaluation.recommended ? 'Deploy OK' : 'Not Recommended'}</div>
            </div>
          </div>
          {result.llmEvaluation.issues.length > 0 && (
            <div className="mb-3">
              <h4 className="text-xs text-gray-500 uppercase tracking-wide mb-2">LLM Issues</h4>
              <ul className="space-y-1">
                {result.llmEvaluation.issues.map((issue, i) => (
                  <li key={i} className="text-sm text-red-400/80 pl-2 border-l-2 border-red-700/40">{issue}</li>
                ))}
              </ul>
            </div>
          )}
          {result.llmEvaluation.strengths.length > 0 && (
            <div>
              <h4 className="text-xs text-gray-500 uppercase tracking-wide mb-2">Strengths</h4>
              <ul className="space-y-1">
                {result.llmEvaluation.strengths.map((s, i) => (
                  <li key={i} className="text-sm text-green-400/80 pl-2 border-l-2 border-green-700/40">{s}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const SAMPLES: Record<string, string> = {
  valid: `from genlayer import *

@allow_storage
class SimpleStorage:
    value: str

    @gl.public.write
    def set(self, new_value: str):
        self.value = new_value

    @gl.public.read
    def get(self) -> str:
        return self.value`,
  invalid_missing_import: `class BadContract:
    @gl.public.write
    def set(self, x: int):
        self.x = x`,
  invalid_bare_except: `from genlayer import *

@allow_storage
class Risky:
    data: str

    @gl.public.write
    def update(self, val: str):
        try:
            self.data = val
        except:
            pass`,
  invalid_stub: `from genlayer import *

@allow_storage
class StubContract:
    count: int

    @gl.public.write
    def increment(self):
        pass

    @gl.public.read
    def get_count(self):
        ...`,
};

function SampleButtons({ onSelect }: { onSelect: (code: string) => void }) {
  return (
    <div className="flex flex-wrap gap-2 mt-3">
      <span className="text-xs text-gray-500 self-center">Load sample:</span>
      {Object.keys(SAMPLES).map((key) => (
        <button key={key} onClick={() => onSelect(SAMPLES[key])} className="px-3 py-1 text-xs rounded-full border border-gray-700/50 text-gray-400 hover:text-gray-200 hover:border-gray-500/50 transition-colors">
          {key === 'valid' ? 'Valid' : key.includes('missing') ? 'No import' : key.includes('bare') ? 'Bare except' : 'Stub'}
        </button>
      ))}
    </div>
  );
}

export function App() {
  const [code, setCode] = useState('');
  const [contractAddress, setContractAddress] = useState('');
  const [result, setResult] = useState<JudgeResult | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [useLLM, setUseLLM] = useState(false);

  const handleJudge = useCallback(async () => {
    if (!code.trim()) { setError('Please enter contract code.'); return; }
    setRunning(true); setError(null); setResult(null);
    try {
      const res = await runJudge(code, contractAddress || undefined, { useLLM, consensusRounds: 3 });
      setResult(res);
    } catch (err: any) { setError(err.message || String(err)); setResult(null); }
    finally { setRunning(false); }
  }, [code, contractAddress]);

  return (
    <div className="min-h-screen bg-gray-950">
      <header className="border-b border-gray-800/80 bg-gray-950/80 backdrop-blur sticky top-0 z-50">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-2xl">⚖️</span>
            <h1 className="text-lg font-semibold tracking-tight">Contract Judge</h1>
            <span className="text-xs text-gray-500 hidden sm:inline">GenLayer</span>
          </div>
          <div className="flex items-center gap-2 text-xs text-gray-500"><span className="w-2 h-2 rounded-full bg-green-500/60 animate-pulse" />Studio Net</div>
        </div>
      </header>
      <main className="max-w-5xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h2 className="text-2xl font-bold mb-2">Test your GenLayer contract</h2>
          <p className="text-gray-400 text-sm max-w-2xl">Paste your contract code below. The judge runs static analysis to check for common issues — missing imports, wrong decorators, bare excepts, stubs, and type annotation gaps. Validators reach consensus on the verdict.</p>
        </div>
        <div className="bg-gray-900/60 border border-gray-800/80 rounded-2xl overflow-hidden mb-6">
          <div className="flex border-b border-gray-800/80">
            <button className="px-6 py-3 text-sm font-medium text-gray-400 border-b-2 border-transparent hover:text-gray-200 transition-colors" onClick={() => setResult(null)}>Code</button>
          </div>
          <div className="p-4">
            <textarea value={code} onChange={e => { setCode(e.target.value); setResult(null); }} placeholder="Paste your GenLayer contract code here..." className="w-full h-72 bg-gray-950/80 border border-gray-700/60 rounded-xl p-4 text-sm font-mono text-gray-200 placeholder-gray-600 focus:outline-none focus:border-gray-600/80 focus:ring-1 focus:ring-gray-600/40 resize-none transition-colors" spellCheck={false} />
            <div className="flex items-center justify-between mt-3 flex-wrap gap-2">
              <SampleButtons onSelect={setCode} />
              <div className="flex items-center gap-3">
                <input type="text" value={contractAddress} onChange={e => setContractAddress(e.target.value)} placeholder="Optional: deployed contract address" className="bg-gray-950/80 border border-gray-700/60 rounded-lg px-3 py-1.5 text-sm font-mono text-gray-300 placeholder-gray-600 focus:outline-none focus:border-gray-600/80 w-56" />
                <label className="flex items-center gap-2 text-xs text-gray-400 cursor-pointer select-none">
                  <input type="checkbox" checked={useLLM} onChange={e => setUseLLM(e.target.checked)} className="rounded border-gray-600 bg-gray-800 text-gray-300 focus:ring-gray-500/50" />
                  LLM Consensus
                </label>
                <button onClick={handleJudge} disabled={running || !code.trim()} className="px-5 py-2 bg-gray-800 hover:bg-gray-700 disabled:bg-gray-800/50 disabled:cursor-not-allowed text-sm font-medium rounded-lg border border-gray-700/50 text-gray-300 hover:text-gray-100 transition-colors flex items-center gap-2">
                  {running ? <><span className="w-4 h-4 border-2 border-gray-500/60 border-t-gray-300 rounded-full animate-spin" />Judging...</> : <>⚖️ Judge Contract</>}
                </button>
              </div>
            </div>
          </div>
        </div>
        {error && <div className="mb-4 px-4 py-3 rounded-xl bg-red-900/20 border border-red-700/40 text-red-400 text-sm">{error}</div>}
        {result && <ResultDisplay result={result} />}
        {!result && !error && code && <div className="mt-6 text-center py-12"><p className="text-gray-600 text-sm">Press "Judge Contract" to run analysis</p></div>}
        {!code && <div className="mt-12 text-center">
          <div className="text-5xl mb-4 opacity-30">⚖️</div>
          <h3 className="text-lg font-medium text-gray-400 mb-2">No contract loaded</h3>
          <p className="text-sm text-gray-600 max-w-md mx-auto">Paste your GenLayer contract code above, or load one of the sample contracts to see the judge in action.</p>
        </div>}
      </main>
      <footer className="border-t border-gray-800/60 mt-12 py-6 text-center text-xs text-gray-600">Contract Judge · Built on GenLayer Studio Net · Static analysis + consensus</footer>
    </div>
  );
}
