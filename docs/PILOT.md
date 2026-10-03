# User pilot protocol

Status: prepared; no human participants have been observed.

Recruit consenting users, assign pseudonymous participant IDs, and counterbalance order across terminal and bridge. Run the same three tasks with comparable scope and the same agent engine/model. Record environment, engine version, task complexity and order separately. Do not pool different models as a product-effect estimate.

1. **Question:** select storage strategy from two options; explain the chosen tradeoff.
2. **Plan:** approve one independent lot, defer a dependent lot, constrain allowed files. Ask the participant to describe exactly what can run.
3. **Correction:** request pause while an action is in flight, add a constraint, revise a dependency, resume. Distinguish the already running action from subsequent ones.

Measure active decision time (exclude periods absent), number of required interruptions, scope comprehension using the participant's own explanation, lost constraints by comparing submission/receipt/executor input, resume attempts/successes, and perceived effort on a 1–7 scale. Ask the participant how they noticed the revision and whether the controls accurately represented execution.

A complete manual observation JSON:

```json
{"participant":"p01","task":"plan","condition":"bridge","active_seconds":90,"interruptions":2,"understood_scope":true,"constraints_lost":0,"resume_attempts":1,"resume_successes":1,"effort":3}
```

This is an illustrative record, not a measured result. Record only actual observations:

```bash
agent-bridge --db reviews.sqlite3 pilot-record REVIEW_ID observation.json
agent-bridge --db reviews.sqlite3 pilot-report REVIEW_ID
agent-bridge --db reviews.sqlite3 metrics REVIEW_ID
```

The report exposes denominators and comparable task labels. It reports no observations when none exist. Compare matched tasks and participant order before interpreting aggregate medians. The approval rate is not a quality target. An observation-only pilot cannot establish causation.

Instrumentation records local event timing/counts without copying task text into metric events. Durable review and conversation records do contain task text, independently of those metrics. Export is voluntary; no telemetry endpoint exists.
