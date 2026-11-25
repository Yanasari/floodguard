# v0.2.16
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

import json

from genlayer import *


class FloodGuard(gl.Contract):
    """
    FloodGuard - Parametric flood insurance claims verified by AI consensus.

    Parametric insurance removes the loss adjuster from the loop: a policy
    pays out when an objectively measurable event (a flood of a given
    severity in a given place on a given date) is shown to have happened.
    The trust problem is the measurement itself - the insurer and the
    policyholder must agree on what the official record says.

    FloodGuard moves that agreement on-chain as a GenLayer Intelligent
    Contract:

    - A policy is opened with fixed parametric terms: the covered location,
      the flood threshold (rainfall in mm within 24h as reported by the
      Indonesian Meteorological Agency, BMKG, or an official BNPB disaster
      report), and the fixed payout amount.
    - When a flood is believed to have occurred, anyone files a claim
      pointing at the public official report page (BMKG / BNPB) as evidence.
    - verify_claim() lets a leader validator fetch the report page and asks
      an LLM whether the report confirms a flood at the policy location on
      the claim date that meets the threshold. The other validators repeat
      the fetch and the judgement independently and accept the leader's
      verdict only if their own verdict matches it exactly (GenLayer's
      equivalence principle applied to the verdict - the reasoning text is
      never compared).
    - The verdict (APPROVED / REJECTED) and the decisive evidence excerpt
      are stored on-chain; record_payout() then closes an approved claim
      with a payout reference.

    Honest scope of this version: FloodGuard is the verification and record
    layer. It does not custody premiums or payouts; settlement happens
    off-chain against the immutable on-chain verdict.
    """

    owner: Address
    claim_count: u256
    claims: TreeMap[str, str]
    history: DynArray[str]

    def __init__(self) -> None:
        self.owner = gl.message.sender_address
        self.claim_count = u256(0)

    # ---------- helpers ----------

    def _load_claim(self, claim_id: str) -> dict:
        raw = self.claims.get(claim_id, "")
        if raw == "":
            raise gl.vm.UserError(f"Unknown claim: {claim_id}")
        return json.loads(raw)

    def _save_claim(self, claim_id: str, claim: dict) -> None:
        self.claims[claim_id] = json.dumps(claim)

    def _log(self, entry: dict) -> None:
        self.history.append(json.dumps(entry))

    # ---------- writes ----------

    @gl.public.write
    def open_policy(
        self,
        holder: str,
        location: str,
        threshold_mm: u256,
        payout_amount: u256,
        asset: str,
    ) -> str:
        """Open a parametric flood policy with fixed terms. Returns its id."""
        self.claim_count = u256(int(self.claim_count) + 1)
        policy_id = "policy-" + str(int(self.claim_count))
        policy = {
            "id": policy_id,
            "holder": holder,
            "location": location,
            "threshold_mm": int(threshold_mm),
            "payout_amount": int(payout_amount),
            "asset": asset,
            "status": "ACTIVE",
        }
        self._save_claim(policy_id, policy)
        self._log({"event": "policy_opened", "policy": policy})
        return policy_id

    @gl.public.write
    def file_claim(
        self, policy_id: str, event_date: str, report_url: str
    ) -> str:
        """File a claim against a policy, pointing at the official report."""
        policy = self._load_claim(policy_id)
        if policy["status"] != "ACTIVE":
            raise gl.vm.UserError(f"Policy {policy_id} is not ACTIVE")
        claim_id = policy_id + "-claim"
        if self.claims.get(claim_id, "") != "":
            raise gl.vm.UserError(f"Claim already filed for {policy_id}")
        claim = {
            "id": claim_id,
            "policy_id": policy_id,
            "holder": policy["holder"],
            "location": policy["location"],
            "threshold_mm": policy["threshold_mm"],
            "payout_amount": policy["payout_amount"],
            "asset": policy["asset"],
            "event_date": event_date,
            "report_url": report_url,
            "status": "PENDING",
            "verdict": "",
            "evidence": "",
        }
        self._save_claim(claim_id, claim)
        self._log({"event": "claim_filed", "claim": claim})
        return claim_id

    @gl.public.write
    def verify_claim(self, claim_id: str) -> None:
        """Judge a filed claim against its official report by consensus."""
        claim = self._load_claim(claim_id)
        if claim["status"] != "PENDING":
            raise gl.vm.UserError(f"Claim {claim_id} is not PENDING")

        report_url = claim["report_url"]
        location = claim["location"]
        event_date = claim["event_date"]
        threshold = claim["threshold_mm"]

        def leader_fn() -> dict:
            page = gl.nondet.web.render(report_url, mode="text")
            prompt = (
                "You are verifying a parametric flood insurance claim.\n"
                f"Covered location: {location}\n"
                f"Claimed flood date: {event_date}\n"
                f"Policy threshold: {threshold} mm of rainfall within "
                "24 hours.\n\n"
                "Below is the content of an official Indonesian disaster "
                "/ weather source (a BNPB DIBI report page, or JSON from "
                "the BMKG public API, where each hourly entry carries "
                '"tp" = precipitation in mm and "datetime" = its UTC '
                "timestamp).\n\n"
                "Decision rule - apply it mechanically:\n"
                "- APPROVED if the precipitation figures for the claimed "
                "date add up to at least the threshold, OR the source "
                "explicitly reports a flood at the covered location on "
                "the claimed date.\n"
                "- REJECTED in every other case.\n"
                "Your verdict MUST agree with the figures you report: "
                "if the total meets the threshold, the verdict is "
                "APPROVED.\n\n"
                "Source content:\n"
                + page[:6000]
                + '\n\nRespond with JSON only: {"verdict": "APPROVED" or '
                '"REJECTED", "evidence": "ONLY the decisive figures, '
                "e.g. 'Rainfall 2026-11-25: 1.7 + 0.4 + 1.1 = 3.2 mm, "
                "threshold 3 mm' - at most 200 characters, no reasoning, "
                'no commentary"}'
            )
            result = gl.nondet.exec_prompt(prompt, response_format="json")
            if result["verdict"] not in ("APPROVED", "REJECTED"):
                raise gl.vm.UserError("Unexpected verdict from leader")
            return result

        def validator_fn(leader_result: gl.vm.Result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False
            leader_verdict = leader_result.calldata["verdict"]
            own = leader_fn()
            return own["verdict"] == leader_verdict

        verdict_data = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)

        claim["verdict"] = verdict_data["verdict"]
        claim["evidence"] = verdict_data["evidence"]
        claim["status"] = (
            "APPROVED" if verdict_data["verdict"] == "APPROVED" else "REJECTED"
        )
        self._save_claim(claim_id, claim)
        self._log(
            {
                "event": "claim_verified",
                "claim_id": claim_id,
                "verdict": claim["verdict"],
                "evidence": claim["evidence"],
            }
        )

    @gl.public.write
    def record_payout(self, claim_id: str, payout_ref: str) -> None:
        """Record the off-chain payout of an APPROVED claim and close it."""
        claim = self._load_claim(claim_id)
        if claim["status"] != "APPROVED":
            raise gl.vm.UserError(f"Claim {claim_id} is not APPROVED")
        claim["status"] = "PAID"
        claim["payout_ref"] = payout_ref
        self._save_claim(claim_id, claim)
        policy = self._load_claim(claim["policy_id"])
        policy["status"] = "SETTLED"
        self._save_claim(claim["policy_id"], policy)
        self._log(
            {
                "event": "payout_recorded",
                "claim_id": claim_id,
                "payout_ref": payout_ref,
            }
        )

    # ---------- views ----------

    @gl.public.view
    def get_claim(self, claim_id: str) -> dict:
        return self._load_claim(claim_id)

    @gl.public.view
    def get_policy(self, policy_id: str) -> dict:
        return self._load_claim(policy_id)

    @gl.public.view
    def get_history(self) -> list:
        return [json.loads(entry) for entry in self.history]

    @gl.public.view
    def get_config(self) -> dict:
        return {
            "owner": str(self.owner),
            "policies_opened": int(self.claim_count),
            "threshold_source": "BMKG / BNPB official public reports",
            "verdicts": ["APPROVED", "REJECTED"],
        }
