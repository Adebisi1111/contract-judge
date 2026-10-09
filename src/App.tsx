import { useState, useCallback } from 'react';
import { runJudge, analyzeStatic, JudgeResult, JudgeIssue } from './judge';
import { connectWallet } from './genlayer-api';

const CONTRACT_ADDRESS = '0x144d4d36C5fE65a834871EE9C2900866157B5A78';

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
        {result.onChain && (
          <div className="mt-3 grid grid-cols-2 gap-3">
            <div className="bg-gray-800/40 rounded-lg p-3 border border-gray-700/40">
              <div className="text-xs text-gray-500 mb-1">On-Chain Severity</div>
              <div className="text-lg font-semibold uppercase">{result.onChain.severity}</div>
            </div>
            <div className="bg-gray-800/40 rounded-lg p-3 border border-gray-700/40">
              <div className="text-xs text-gray-500 mb-1">Recommended</div>
              <div className="text-lg font-semibold">{result.onChain.recommended ? 'Deploy OK' : 'Not Recommended'}</div>
            </div>
          </div>
        )}
        {result.onChain && (
          <div className="mt-3 text-xs text-gray-500 space-y-1">
            <p>Submission ID: <code className="text-gray-400">{result.onChain.submissionId}</code></p>
            <p>Analyzer: <code className="text-gray-400">{result.onChain.analyzer}</code></p>
            <p>Tx: <code className="text-gray-400">{result.onChain.txHash.slice(0, 20)}...</code></p>
          </div>
        )}
      </div>
      {result.issues.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wide mb-3">Issues ({result.issues.length})</h3>
          <div className="space-y-1">{result.issues.map((issue, i) => <IssueChip key={i} issue={issue} />)}</div>
        </div>
      )}
      {result.onChain && result.onChain.strengths.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wide mb-3">Strengths</h3>
          <ul className="space-y-1">
            {result.onChain.strengths.map((s, i) => (
              <li key={i} className="text-sm text-green-400/80 pl-2 border-l-2 border-green-700/40">{s}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

const SAMPLES: Record<string, string> = {
  valid: `from genlayer import *\n\n@allow_storage\nclass SimpleStorage:\n    value: str\n\n    @gl.public.write\n    def set(self, new_value: str):\n        self.value = new_value\n\n    @gl.public.view\n    def get(self) -> str:\n        return self.value`,
  invalid_missing_import: `class BadContract:\n    @gl.public.write\n    def set(self, x: int):\n        self.x = x`,
  invalid_bare_except: `from genlayer import *\n\n@allow_storage\nclass Risky:\n    data: str\n\n    @gl.public.write\n    def update(self, val: str):\n        try:\n            self.data = val\n        except:\n            pass`,
  invalid_stub: `from genlayer import *\n\n@allow_storage\nclass StubContract:\n    count: int\n\n    @gl.public.write\n    def increment(self):\n        pass\n\n    @gl.public.view\n    def get_count(self):\n        ...`,
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
  const [result, setResult] = useState<JudgeResult | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [wallet, setWallet] = useState<string | null>(null);
  const [staticPreview, setStaticPreview] = useState<JudgeIssue[] | null>(null);

  const handleConnect = useCallback(async () => {
    try {
      const addr = await connectWallet();
      setWallet(addr);
      setError(null);
    } catch (err: any) {
      setError(err.message || String(err));
    }
  }, []);

  const handleJudge = useCallback(async () => {
    if (!code.trim()) { setError('Please enter contract code.'); return; }
    if (!wallet) { setError('Connect wallet first.'); return; }
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      // Quick static preview while on-chain tx is submitted
      const preview = analyzeStatic(code);
      setStaticPreview(preview);
      const res = await runJudge(code, wallet, CONTRACT_ADDRESS);
      setResult(res);
      setStaticPreview(null);
    } catch (err: any) {
      setError(err.message || String(err));
      setResult(null);
    } finally {
      setRunning(false);
    }
  }, [code, wallet]);

  return (
    <div className="min-h-screen bg-gray-950">
      <header className="border-b border-gray-800/80 bg-gray-950/80 backdrop-blur sticky top-0 z-50">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <img src="/logo.svg" alt="Contract Judge" className="h-8 w-auto" />
            <h1 className="text-lg font-semibold tracking-tight">Contract Judge</h1>
            <span className="text-xs text-gray-500 hidden sm:inline">GenLayer Bradbury</span>
          </div>
          <div className="flex items-center gap-3">
            {wallet ? (
              <span className="text-xs text-green-400 font-mono">{wallet.slice(0, 8)}...{wallet.slice(-6)}</span>
            ) : (
              <button onClick={handleConnect} className="px-4 py-1.5 text-xs font-medium rounded-lg border border-gray-700/50 text-gray-300 hover:text-gray-100 hover:border-gray-500/50 transition-colors">
                Connect Wallet
              </button>
            )}
            <span className="text-xs text-gray-500"><span className="w-2 h-2 rounded-full bg-green-500/60 animate-pulse inline-block mr-1" />Bradbury</span>
          </div>
        </div>
      </header>
      <main className="max-w-5xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h2 className="text-2xl font-bold mb-2">On-chain GenLayer contract judge</h2>
          <p className="text-gray-400 text-sm max-w-2xl">Paste your contract code below. The judge submits it to the on-chain ContractJudge contract. AI validators reach consensus on the verdict. Connect your wallet to submit.</p>
        </div>
        <div className="bg-gray-900/60 border border-gray-800/80 rounded-2xl overflow-hidden mb-6">
          <div className="flex border-b border-gray-800/80">
            <button className="px-6 py-3 text-sm font-medium text-gray-400 border-b-2 border-transparent hover:text-gray-200 transition-colors" onClick={() => setResult(null)}>Code</button>
          </div>
          <div className="p-4">
            <textarea value={code} onChange={e => { setCode(e.target.value); setResult(null); setStaticPreview(null); }} placeholder="Paste your GenLayer contract code here..." className="w-full h-72 bg-gray-950/80 border border-gray-700/60 rounded-xl p-4 text-sm font-mono text-gray-200 placeholder-gray-600 focus:outline-none focus:border-gray-600/80 focus:ring-1 focus:ring-gray-600/40 resize-none transition-colors" spellCheck={false} />
            <div className="flex items-center justify-between mt-3 flex-wrap gap-2">
              <SampleButtons onSelect={setCode} />
              <button onClick={handleJudge} disabled={running || !code.trim() || !wallet} className="px-5 py-2 bg-gray-800 hover:bg-gray-700 disabled:bg-gray-800/50 disabled:cursor-not-allowed text-sm font-medium rounded-lg border border-gray-700/50 text-gray-300 hover:text-gray-100 transition-colors flex items-center gap-2">
                {running ? <><span className="w-4 h-4 border-2 border-gray-500/60 border-t-gray-300 rounded-full animate-spin" />Judging on-chain...</> : <>⚖️ Judge Contract</>}
              </button>
            </div>
          </div>
        </div>
        {error && <div className="mb-4 px-4 py-3 rounded-xl bg-red-900/20 border border-red-700/40 text-red-400 text-sm">{error}</div>}
        {staticPreview && !result && running && (
          <div className="mb-4">
            <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wide mb-2">Static preview (on-chain analysis running...)</h3>
            {staticPreview.length === 0 ? (
              <p className="text-sm text-gray-500">No obvious static issues.</p>
            ) : (
              <div className="space-y-1">{staticPreview.map((issue, i) => <IssueChip key={i} issue={issue} />)}</div>
            )}
          </div>
        )}
        {result && <ResultDisplay result={result} />}
        {!result && !error && code && !running && <div className="mt-6 text-center py-12"><p className="text-gray-600 text-sm">Connect wallet and press "Judge Contract" to submit on-chain</p></div>}
        {!code && <div className="mt-12 text-center">
          <img src="/logo.svg" alt="Contract Judge" className="h-20 w-auto mb-4 opacity-30 mx-auto" />
          <h3 className="text-lg font-medium text-gray-400 mb-2">No contract loaded</h3>
          <p className="text-sm text-gray-600 max-w-md mx-auto">Paste your GenLayer contract code above, or load a sample to see the on-chain judge in action.</p>
        </div>}
      </main>
      <footer className="border-t border-gray-800/60 mt-12 py-6 text-center text-xs text-gray-600">Contract Judge · On-chain LLM consensus via GenLayer Bradbury</footer>
    </div>
  );
}
