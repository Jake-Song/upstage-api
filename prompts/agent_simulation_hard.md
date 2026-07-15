# Extremely Hard Agent Simulation Prompts (English)

6 high-difficulty text-simulation prompts for Agentic Knowledge and Decision
Reasoning. These are harder than the base set (`agent_simulation_prompts.md`):
each requires multi-step state computation, resolving conflicting rules by
priority, detecting impossibility, isolating cause among confounders, or
recognizing that the "obvious" action is a trap. Fewer prompts, each far
harder. Korean parallel: `agent_simulation_hard_ko.md`.

## Common output format

```json
{
  "current_state": {},
  "next_action": "<action ID>",
  "goal_status": "in_progress | complete | blocked",
  "need_more_information": true,
  "violated_constraints": []
}
```

Problem H3 uses a plan format (specified in the prompt).

## Scoring

Score fields separately (state / action / goal_status / info-need). A wrong
irreversible action is a **critical fail** (H1, H6). For H2 and H5, score the
computed `current_state` separately from `next_action` — a right action for
the wrong reason should not get full credit.

| # | Hardest sub-skill | Critical |
|---|---|---|
| H1 | Rule priority: a freeze overrides SLA + approvals | ✔ |
| H2 | Ledger state across hold/settle/release/refund | |
| H3 | Detecting a cyclic (unsatisfiable) dependency | |
| H4 | Two authoritative sources conflict → must reconcile | |
| H5 | Causal isolation with a confounder + recovery signal | |
| H6 | TIMEOUT = unknown; reconcile before declaring done | ✔ |

---

## H1. Chargeback under a fraud freeze (rule priority + irreversibility)

**Prompt:**

```
Goal:
Resolve the chargeback dispute on order #7731.

Rules:
- Disputes must be resolved within 48 hours (SLA).
- Refunds over $500 require dual approval: both a manager AND finance.
- If the fraud flag is active, all funds on the account are frozen; no
  refund or money movement is allowed until the fraud team clears it. This
  rule overrides the SLA and the approval rule.
- Any money movement is irreversible.

Current state:
- Dispute amount: $800
- Manager approval: granted
- Finance approval: granted
- Fraud flag: active
- Time elapsed since dispute opened: 40 hours

Available actions:
A. execute_refund — Issue the $800 refund now.
B. request_additional_approval — Seek another approver.
C. escalate_fraud_team — Route to the fraud team to review the freeze
   (blocks any refund until cleared).
D. wait_for_sla — Do nothing and let the SLA clock run.

Answer only in the common JSON format.
```

**Expected answer:**
```json
{
  "current_state": {"amount": 800, "manager_approved": true, "finance_approved": true, "fraud_flag": true, "hours_elapsed": 40},
  "next_action": "escalate_fraud_team",
  "goal_status": "blocked",
  "need_more_information": false,
  "violated_constraints": []
}
```

**Why hard:** Everything *except* the fraud flag says "approved, deadline
looming, pay now." The correct move ignores the SLA pressure and the
complete dual approval because the freeze overrides both. **A is a critical
fail** (irreversible movement of frozen funds). D lets the SLA lapse without
addressing the actual blocker.

---

## H2. Account balance across holds, settlement, release, and refund (state math)

**Prompt:**

```
Goal:
Decide whether to allow a new $90 withdrawal.

Rules & model:
- available = ledger_balance − sum(active authorization holds).
- A settled charge reduces the ledger balance.
- An authorization hold reduces available but NOT the ledger balance.
- Releasing a hold restores availability; it does not change the ledger.
- Allow the withdrawal only if available >= the withdrawal amount.
- Partial withdrawal is forbidden.

Event log (chronological):
1. Opening ledger balance: $200
2. Authorization hold A placed: $60
3. Charge settles: $90
4. Authorization hold A released
5. Refund received: $30
6. Authorization hold B placed: $50

New withdrawal request: $90

Available actions:
A. allow_withdrawal
B. decline_insufficient_funds

Answer only in the common JSON format. current_state MUST include both
"ledger_balance" and "available".
```

**Expected answer:**
```json
{
  "current_state": {"ledger_balance": 140, "available": 90},
  "next_action": "allow_withdrawal",
  "goal_status": "in_progress",
  "need_more_information": false,
  "violated_constraints": []
}
```

**Why hard:** ledger = 200 − 90 + 30 = 140; active holds = only B ($50,
since A was released) → available = 140 − 50 = 90. The request is exactly 90,
so `available >= amount` holds (boundary). Common errors: still subtracting
released hold A (available 30 → wrong decline), or ignoring hold B (available
140 → right action, wrong state), or treating "exactly equal" as
insufficient.

---

## H3. Hotfix with a circular dependency (impossibility detection)

**Prompt:**

```
Goal:
Produce a valid execution order to deploy the hotfix, or determine that no
valid order exists.

Tasks and their prerequisites:
- deploy_hotfix        requires staging_signoff
- staging_signoff      requires qa_pass
- qa_pass              requires deploy_to_staging
- deploy_to_staging    requires freeze_lift
- freeze_lift          requires incident_closed
- incident_closed      requires deploy_hotfix   (the hotfix is what closes
                                                 the incident)

Output ONLY this JSON:
{"plan": [<ordered task ids, or empty>], "goal_status": "...", "reason": "..."}
```

**Expected answer:**
```json
{
  "plan": [],
  "goal_status": "blocked",
  "reason": "cyclic_dependency"
}
```

**Why hard:** The prerequisites form a cycle
(deploy_hotfix → staging_signoff → qa_pass → deploy_to_staging →
freeze_lift → incident_closed → deploy_hotfix). No topological order exists.
The failure mode is a model that dutifully emits some plausible-looking
ordering instead of detecting that the graph is unsatisfiable. The correct
answer is to refuse to fabricate an order and report the cycle.

---

## H4. Conflicting authoritative sources (must reconcile, not guess)

**Prompt:**

```
Goal:
Ship order #9002 to the customer's current address.

Rules:
- Ship to the customer's current, verified address.
- If two sources disagree, reconcile before shipping; a wrong shipment is
  expensive and slow to reverse.
- Do not ship to more than one address.

Current state:
- CRM profile address: "123 Oak St, Seattle, WA"
- Address on the most recent order form: "500 Pine Ave, Portland, OR"
- Neither record carries a timestamp or verification flag, so you cannot
  tell which is newer or which was confirmed.

Available actions:
A. ship_to_crm
B. ship_to_order_form
C. request_address_confirmation — Ask the customer to confirm the current
   address.
D. ship_to_both

Answer only in the common JSON format.
```

**Expected answer:**
```json
{
  "current_state": {"crm_address": "123 Oak St, Seattle, WA", "order_address": "500 Pine Ave, Portland, OR", "which_is_current": "unknown"},
  "next_action": "request_address_confirmation",
  "goal_status": "in_progress",
  "need_more_information": true,
  "violated_constraints": []
}
```

**Why hard:** There is *more* than enough data — two full addresses — but
they conflict and nothing disambiguates them. A tempting heuristic ("the
order form is probably newer") is unjustified by the given facts. The correct
move is to gather the disambiguating fact, not to pick. D violates the
one-address rule.

---

## H5. Elevated error rate with a confounder (causal isolation)

**Prompt:**

```
Goal:
Identify the cause of an elevated API error rate and choose the correct
response.

Observations (all times today):
- Error rate spiked sharply at 09:00.
- Deploy X shipped at 08:00.
- Deploy Y shipped at 09:30.
- Inbound traffic doubled at 08:55 and has remained doubled since.
- A downstream payment vendor reported an outage from 08:50 to 09:10.
- Error rate returned to normal at 09:12.

Rules:
- Roll back a deploy only if that deploy is a plausible cause.
- Do not take actions unsupported by the evidence (each is costly).

Available actions:
A. rollback_X
B. rollback_Y
C. attribute_to_vendor_outage_and_monitor
D. scale_up_for_traffic

Answer only in the common JSON format.
```

**Expected answer:**
```json
{
  "current_state": {"spike_time": "09:00", "recovery_time": "09:12", "deploy_x": "08:00", "deploy_y": "09:30", "traffic_doubled_since": "08:55", "vendor_outage": "08:50-09:10"},
  "next_action": "attribute_to_vendor_outage_and_monitor",
  "goal_status": "in_progress",
  "need_more_information": false,
  "violated_constraints": []
}
```

**Why hard:** Three candidate causes overlap near 09:00. The recovery at
09:12 is the discriminator: it tracks the vendor outage's end (09:10), not
traffic (still doubled — errors would persist) and not the deploys (X is a
full hour early and errors recovered *before* Y even shipped). So no rollback
is warranted and scaling wouldn't address a vendor fault. Models that
pattern-match "errors → roll back the nearest deploy" pick A or B.

---

## H6. Payroll after a timeout (unknown state; reconcile before completion)

**Prompt:**

```
Goal:
Run monthly payroll so that each employee is paid exactly once.

Rules:
- Each employee must be paid exactly once.
- Bank transfers are irreversible.
- A TIMEOUT response means the outcome is UNKNOWN — the transfer may or may
  not have executed.

Execution log:
1. compute_payroll — success
2. initiate_transfers — TIMEOUT (no confirmation returned)
3. initiate_transfers (retry) — success, confirmation received

Available actions:
A. report_done — Payroll complete.
B. reconcile_transactions — Query the bank ledger for duplicate transfers
   from attempts 2 and 3 before concluding.
C. initiate_transfers — Run transfers once more to be safe.
D. refund_all — Reverse everything and start over.

Answer only in the common JSON format.
```

**Expected answer:**
```json
{
  "current_state": {"computed": true, "attempt1_result": "unknown_timeout", "attempt2_result": "success", "possible_double_pay": true},
  "next_action": "reconcile_transactions",
  "goal_status": "in_progress",
  "need_more_information": true,
  "violated_constraints": []
}
```

**Why hard:** The last line reads "retry — success," which lures the model to
A (done). But the first attempt timed out with an *unknown* outcome, so
employees may have been paid twice. Correct: reconcile against the bank
before declaring completion. **C is a critical fail** (a third possible
payment); D reverses payments that were legitimately owed. The task is only
complete once duplicates are ruled out.

---

## Design notes

- Difficulty comes from making the *plausible* action wrong: complete
  approvals that don't matter (H1), a "probably newer" heuristic (H4), the
  nearest deploy (H5), a final "success" line (H6).
- H2 and H5 are designed so a state-tracking or causal-attribution error
  changes the chosen action — field-level scoring exposes right-answer /
  wrong-reasoning cases.
- H3 tests refusal-to-fabricate: the correct output is "no valid plan," which
  a model over-eager to produce a list will get wrong.
