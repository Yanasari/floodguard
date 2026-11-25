# FloodGuard — Parametric Flood Insurance Claims Verified by AI Consensus

FloodGuard is a GenLayer **Intelligent Contract** that verifies
parametric flood insurance claims against official Indonesian data.
In parametric insurance there is no loss adjuster: a policy pays out
when an objectively measurable event — a flood of a given severity in
a given place on a given date — is shown to have happened. The hard
part is the measurement itself: the insurer and the policyholder must
agree on what the official record says. FloodGuard moves that
agreement on-chain, where GenLayer's validators read the official
record themselves and reach consensus on the verdict.

## The problem

Indonesia floods every rainy season, and conventional flood claims
are slow: paperwork, site surveys, and disputes over whether a given
house was really inundated and how badly. Parametric products fix the
payout in advance against a measurable trigger — but then everything
depends on the trigger data being read the same way by everyone.
A classic smart contract cannot open a BMKG rainfall feed or a BNPB
disaster report. FloodGuard can: the evidence is a public official
page, and the "adjuster" is a validator consensus.

## How it works

1. **Open a policy** — the insurer records the parametric terms
   on-chain: policyholder, covered location, the flood threshold
   (rainfall in mm within 24 hours), and the fixed payout amount and
   asset.
2. **File a claim** — after a flood, a claim is filed against the
   policy with the event date and the URL of the official evidence:
   a BNPB DIBI disaster report page, or the BMKG public API response
   for the covered village-level area (`api.bmkg.go.id`, whose hourly
   entries carry `tp` = precipitation in mm).
3. **Verify the claim** — a leader validator fetches the evidence
   (`gl.nondet.web.render`) and asks an LLM whether it confirms a
   flood at the covered location on the claim date meeting the
   threshold (`gl.nondet.exec_prompt`, JSON response). Every other
   validator independently repeats the fetch and the judgement, and
   accepts the leader's verdict only if its own verdict matches it
   **exactly** (`gl.vm.run_nondet_unsafe` with a custom validator) —
   GenLayer's equivalence principle applied to the verdict
   (`APPROVED` / `REJECTED`); the reasoning text is never compared.
4. **Pay out** — the verdict and the decisive evidence excerpt are
   stored on-chain; `record_payout` records the settlement reference
   and closes the claim. Every step is appended to a public,
   append-only history (`get_history`).

The evidence page is treated as untrusted input throughout: its
content is fenced inside the judging prompt as data only.

## Contract API

| Method | Type | Description |
| --- | --- | --- |
| `open_policy(holder, location, threshold_mm, payout_amount, asset)` | write | Open a parametric policy with fixed terms; returns the policy id |
| `file_claim(policy_id, event_date, report_url)` | write | File a claim pointing at the official BMKG/BNPB evidence |
| `verify_claim(claim_id)` | write | Fetch evidence + LLM judgement + validator consensus on APPROVED / REJECTED |
| `record_payout(claim_id, payout_ref)` | write | Record the payout of an APPROVED claim; settles the policy |
| `get_policy(policy_id)` | view | Full policy record |
| `get_claim(claim_id)` | view | Full claim record: terms, evidence, verdict, status |
| `get_history()` | view | Append-only log of every event (JSON) |
| `get_config()` | view | Contract configuration and data sources |

Constructor: `FloodGuard()` — no arguments. The deployer becomes the
contract owner.

Claim lifecycle: `PENDING` → `APPROVED` / `REJECTED` → `PAID`
(policy `ACTIVE` → `SETTLED`).

## Live demo (GenLayer Studio / Studionet)

<!-- DEMO-PROOF:BEGIN -->
- Contract: `flood_guard.py`
- Network: GenLayer Studio (Studionet)
- Contract address: _to be filled after deployment_
- Deploy tx: _to be filled after deployment_
- Demo policy + claim: _to be filled after the live run_
<!-- DEMO-PROOF:END -->

## Honest limitations

- **v1 is the verification and record layer.** It stores policies,
  claims, verdicts and payout records. Holding premiums and executing
  payouts on-chain is the next step, the same way a court's judgment
  precedes enforcement.
- **Evidence must be fetchable by validators.** The BMKG public API
  and BNPB's DIBI portal are publicly readable; pages behind bot
  protection cannot be judged, and if validators cannot agree, the
  verification transaction reverts and no verdict is written — the
  contract prefers no verdict over a disputed one.
- **Thresholds are read from the official record.** BMKG API data is
  a forecast/observation feed per administrative area; a claim is
  judged against the location and date written into the policy, so
  policy terms should name the area precisely (village-level `adm4`
  for BMKG API evidence).

## Relationship to the author's other GenLayer work

FloodGuard is an original project by the same author as EscrowCourt
(Internet Court dispute resolution for x402 agent jobs), HargaPangan
(an AI web oracle for Indonesian staple food prices) and ArisanChain
(transparent rotating savings groups). Where HargaPangan applies
validator consensus to a number extracted from a web page, FloodGuard
applies the same equivalence pattern to an insurance verdict over
official disaster data.
