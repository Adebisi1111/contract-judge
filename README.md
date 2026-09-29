# Contract Judge

A GenLayer dApp that lets users submit Python contract code for LLM-powered security analysis.
Validators reach consensus on the LLM's verdict — the "validator as judge" pattern.

## Architecture

```
┌──────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Frontend   │────▶│  GenLayer Router │────▶│  ContractJudge  │
│  (React+Vite) │     │  (genlayer-js)   │     │ (LLM + consensus)│
└──────────────┘     └──────────────────┘     └─────────────────┘
                                                        │
                                                ▼       ▼       ▼
                                          Validator  Validator  Validator
                                          (LLM)      (LLM)      (LLM)
```

**Frontend** (`src/`): React + Vite + Tailwind. Submits contract code to the judge contract
and displays the LLM's analysis with severity breakdown and consensus info.

**Smart Contract** (`contracts/judge_contract.py`): GenLayer contract that accepts submitted
Python code, runs it through `gl.nondet.exec_prompt` for LLM analysis, and stores the verdict.
Validators independently execute the LLM call and reach consensus on the result.

**LLM Evaluation** (`src/llm.ts`): Frontend-side LLM evaluation via the inference API.
Runs multiple rounds and checks consensus (agree/partial/disagree) before presenting results.

## Quick Start

```bash
cd contract-judge

# Start the frontend dev server
npm run dev

# Open http://localhost:5173
```

## Usage

1. **Paste contract code** into the editor, or load a sample
2. **Check "LLM Consensus"** to run multi-round LLM analysis (optional, slower)
3. Click **"Judge Contract"**
4. View the results:
   - Static analysis issues (always shown)
   - LLM consensus panel (if enabled): consensus level, recommendation, LLM issues/strengths

## Sample Contracts

| Sample | Description |
|---|---|
| Valid | Clean, well-formed GenLayer contract |
| No import | Missing `from genlayer import` |
| Bare except | Uses bare `except:` clause |
| Stub | Methods with only `pass`/`...` |

## Judge Contract

The `ContractJudge` smart contract provides:

| Method | Description |
|---|---|
| `submit_contract(code)` | Submit contract code for analysis. Returns submission ID. |
| `analyze(submission_id)` | Run LLM analysis. Validators consensus on the result. |
| `get_verdict(submission_id)` | Read the stored verdict and full submission record. |
| `list_submissions()` | List all submission IDs and statuses. |
| `get_stats()` | Usage statistics (total, analyzed, pending). |

The LLM prompt analyzes for: missing imports, wrong decorators, storage issues, reentrancy,
error handling, type safety, logic bugs, non-determinism risks, and prompt injection risks.

## Tech Stack

- **Frontend:** React 19, Vite 6, Tailwind CSS 4, TypeScript
- **Blockchain:** GenLayer Studio Net, genlayer-js SDK, viem
- **LLM:** Inference API (Claude Sonnet) for multi-round consensus evaluation
- **Build:** npm, TypeScript strict mode

## Project Structure

```
contract-judge/
├── contracts/
│   └── judge_contract.py      # GenLayer judge contract
├── src/
│   ├── App.tsx                # Main React UI
│   ├── judge.ts               # Static analysis + judge orchestration
│   ├── llm.ts                 # LLM evaluation + consensus
│   ├── genlayer-api.ts         # GenLayer RPC client
│   ├── main.tsx               # Entry point
│   ├── index.css              # Tailwind + custom styles
│   └── vite-env.d.ts          # Vite type declarations
├── index.html                 # HTML entry
├── vite.config.ts             # Vite config (React + Tailwind plugins)
├── tsconfig.json              # TypeScript config (strict)
├── package.json               # Dependencies
└── README.md                  # This file
```

## License

MIT
