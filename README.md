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
- Deployed from (owner): `0x0d1e8B737614bCb563A4BaB329bC257D200B42B4`
- Contract address: `0xcF5d83Cae518E1908b381b474892Fd00EFC0050F`
  ([explorer](https://explorer-studio.genlayer.com/address/0xcF5d83Cae518E1908b381b474892Fd00EFC0050F))
- Deploy tx: `0x2480f79250929d889b2582ce8af3e7e956be92b3d9eb84a2871bdc3da610ecd0` — FINALIZED, 2026-11-25

Demo policy `policy-1` — holder "Yanna", location "Gambir, Jakarta
Pusat, DKI Jakarta, Indonesia", payout 1000 USDC. The demo trigger is
2 mm so the full lifecycle can be exercised end-to-end on a light-rain
day; a production policy would set a flood-scale threshold.

Demo claim `policy-1-claim` — event date 2026-11-25, evidence: the
BMKG public API response for Gambir
(`https://api.bmkg.go.id/publik/prakiraan-cuaca?adm4=31.71.01.1001`):

| Step | Tx | Result |
| --- | --- | --- |
| `open_policy` | `0x833d7ff73c36b82106f12830136cb80bccbc5b91ebd70f03198837272e787e25` | FINALIZED, policy id `policy-1` |
| `file_claim` | `0xdb8f498eb12de65a12b8ed0b718325aef4d1af2dc3375900119de2b59bdf12d8` | FINALIZED, claim id `policy-1-claim` |
| `verify_claim` | `0x6016432ebb06bce1ad380c5b7c68cb3ae63d29aec7f64e16d4fdbf8c446d56d9` | FINALIZED — verdict **APPROVED** |
| `record_payout` (`demo-payout-001`) | `0x84ecd07ecf05d6b3ff566efb582f1b37c8e71b9525ec7b97f2abf86267ca8c42` | FINALIZED — claim **PAID** |

Verdict evidence recorded on-chain: *"Rainfall data for 2026-11-25
includes entries with precipitation (tp): 1.7 mm at 15:00 UTC, 0.4 mm
at 18:00 UTC, and 1.1 mm at 21:00 UTC, exceeding the 2 mm threshold
within 24 hours."*
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
