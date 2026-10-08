# Contract Judge

A GenLayer dApp where users submit Python contract code for on-chain LLM-powered security analysis. AI validators reach consensus on the verdict — the "validator as judge" pattern.

## Deployed

- **Network:** GenLayer Bradbury Testnet (chain 4221)
- **Contract:** `0x19D67d618b32BF872b4D57463664D792d2E3C598`
- **Explorer:** https://explorer-bradbury.genlayer.com/address/0x19D67d618b32BF872b4D57463664D792d2E3C598

## Architecture

```
┌──────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│   Frontend   │────▶│  GenLayer Router │────▶│   ContractJudge     │
│  (React+Vite)│     │  (eth_sendTx)    │     │ (LLM + consensus)   │
└──────────────┘     └──────────────────┘     └─────────────────────┘
                              │                         │
                      submit_contract          analyze() → run_nondet
                      (write tx)               (write tx + LLM)
                                                     │
                                              get_verdict()
                                              (read call)
```

## On-Chain Flow

1. **Connect Wallet** — app auto-switches to Bradbury (4221)
2. **submit_contract(code)** — write tx stores the code, returns submission ID
3. **analyze(submission_id)** — write tx triggers `gl.vm.run_nondet` with leader/validator LLM consensus
4. **get_verdict(submission_id)** — read call returns severity, issues, strengths, recommendation

## Contract API

| Method | Type | Description |
|---|---|---|
| `submit_contract(code)` | write | Submit contract code. Returns submission ID. |
| `analyze(submission_id)` | write | Run LLM analysis with validator consensus. Returns severity. |
| `get_verdict(submission_id)` | view | Read stored verdict: severity, issues, strengths, recommendation. |
| `list_submissions()` | view | List all submission IDs and statuses. |
| `get_stats()` | view | Usage statistics. |

## LLM Consensus

The `analyze()` method runs `gl.vm.run_nondet` with a leader/validator pattern:
- Leader calls `gl.nondet.exec_prompt` with the contract code and a structured JSON prompt
- Each validator independently runs the same LLM analysis
- Majority agreement on `severity` is required for the verdict to be committed

The LLM checks for: missing imports, missing @allow_storage, wrong decorators, missing return types, bare excepts, stub methods, mutable defaults, prompt injection risks, collection storage fields, @staticmethod, and local imports.

## Tech Stack

- **Contract:** Python GenLayer Intelligent Contract (GenVM runner `1jb45aa8...`)
- **Consensus:** `gl.vm.run_nondet` leader/validator pattern
- **AI:** `gl.nondet.exec_prompt` for on-chain LLM analysis
- **Frontend:** React 19, Vite 6, Tailwind CSS 4, TypeScript
- **Write Tx:** Direct `eth_sendTransaction` with GenLayer ULEB128 calldata encoding
- **Read Tx:** `gen_call` JSON-RPC

## Project Structure

```
contract-judge/
├── contracts/
│   └── judge_contract.py    # On-chain judge contract
├── src/
│   ├── App.tsx              # Main React UI (wallet connect + on-chain judge)
│   ├── judge.ts             # On-chain judge orchestration + static preview
│   ├── genlayer-api.ts      # GenLayer RPC client (read + write)
│   ├── main.tsx             # Entry point
│   ├── index.css            # Tailwind styles
│   └── vite-env.d.ts        # Vite types
├── index.html               # HTML entry
├── vite.config.ts           # Vite config
├── tsconfig.json            # TypeScript config
└── package.json             # Dependencies
```

## Verified On-Chain

- `submit_contract` with a valid contract → accepted, submission ID "0"
- `analyze("0")` → MAJORITY_AGREE consensus, verdict stored
- `get_verdict("0")` → severity "none", 11 strengths listed, recommended true
- Full lifecycle verified on Bradbury Testnet

## License

MIT
