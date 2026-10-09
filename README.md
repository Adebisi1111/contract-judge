# Contract Judge

A GenLayer dApp where users submit Python contract code for on-chain LLM-powered security analysis. AI validators reach consensus on the verdict — the "validator as judge" pattern.

## Deployed

- **Network:** GenLayer Bradbury Testnet (chain 4221)
- **Contract:** `0x144d4d36C5fE65a834871EE9C2900866157B5A78`
- **Explorer:** https://explorer-bradbury.genlayer.com/address/0x144d4d36C5fE65a834871EE9C2900866157B5A78

> The deployed address is written to `deployed_addresses.json` by the
> verification script on each run; see "Verification" below.

## Architecture

```
┌──────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│   Frontend   │────▶│  genlayer-js SDK │────▶│   ContractJudge     │
│  (React+Vite)│     │  (official SDK)  │     │ (LLM + consensus)   │
└──────────────┘     └──────────────────┘     └─────────────────────┘
```

## On-Chain Flow

1. **Connect Wallet** — app uses the official `genlayer-js` SDK client bound to Bradbury (4221)
2. **submit_contract(code)** — write tx stores the code, returns submission ID
3. **analyze(submission_id)** — write tx triggers `gl.vm.run_nondet` with leader/validator LLM consensus
4. **get_verdict(submission_id)** — decoded read returns severity, issues, strengths, recommendation

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
- Leader calls `gl.nondet.exec_prompt` (with `response_format="json"`) on the contract code
- Each validator independently re-runs the analysis
- Consensus compares a **coarse verdict bucket** (`blocking` = critical/high, `ok` = everything
  else) rather than the exact severity label — two LLM runs on identical code can disagree on
  "critical" vs "high" but agree the contract is unsafe. Exact-label matching produced
  `NO_MAJORITY`; bucket matching reaches consensus reliably while still rejecting genuine
  disagreement.

The verdict JSON is defensively parsed: markdown fences stripped, the outer `{}` extracted,
`issues`/`strengths` normalized to string lists, and a keyword fallback if parsing fails.

## Verification (repeatable, repository-local)

`scripts/verify_workflow.mjs` is a standalone diagnostic that uses **only the official
genlayer-js SDK** (no custom transport). It:

1. Deploys `contracts/judge_contract.py` to Bradbury
2. Verifies transaction execution status on every write (`status_name`,
   `txExecutionResultName`, `resultName`)
3. Decodes contract reads (`get_stats`, `get_verdict`)
4. Runs the full `submit_contract → analyze → get_verdict` workflow on both a clean and a
   flawed contract
5. Writes the resulting address to `deployed_addresses.json`

Run it:

```bash
export JUDGE_PRIVATE_KEY=0x...   # a key funded on Bradbury (https://faucet.genlayer.foundation)
node scripts/verify_workflow.mjs
```

### Verified on-chain

- **Deploy** → `ACCEPTED` / `FINISHED_WITH_RETURN` / `AGREE`; ~10KB of code on-chain
- **submit_contract** → `AGREE`; `get_stats` decodes `total_submissions`
- **analyze** → reaches `AGREE` consensus and commits the verdict (a flawed
  contract with `@staticmethod` + a local import was correctly flagged
  `severity: high`, `recommended: false`, with both issues listed)
- **get_verdict** → decodes the full stored record (`status: analyzed`,
  severity, issues, strengths, recommendation, analyzer)
- Full `submit_contract → analyze → get_verdict` lifecycle confirmed on Bradbury

> Note: `analyze` is an LLM consensus round and is non-deterministic. Individual
> rounds can return `NO_MAJORITY`, `VALIDATORS_TIMEOUT`, or `LEADER_TIMEOUT`
> before one reaches `AGREE`; the workflow script retries and reports the raw
> execution status on each write so the outcome is always visible.

## Tech Stack

- **Contract:** Python GenLayer Intelligent Contract (GenVM runner `1jb45aa8...`)
- **Consensus:** `gl.eq_principle.prompt_comparative` (leader/validator, bucket-equivalent verdict)
- **AI:** `gl.nondet.exec_prompt` with `response_format="json"`
- **Frontend:** React 19, Vite 6, Tailwind CSS 4, TypeScript
- **Transport:** official `genlayer-js` SDK (`createClient`, `deployContract`,
  `writeContract`, `readContract`, `waitForTransactionReceipt`)

## License

MIT
