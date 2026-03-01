# CLI Quick Start - 5 Minutes

## Try These 5 Commands Right Now

### 1. Process a simple claim (auto-approves)
```bash
python -m src.cli.main process scenario_01_minor_scratch_auto_approve.json
```
**Result:** ✓ Complete, Approved ✓ Yes, ~€111

---

### 2. Process a claim that needs review (pauses workflow)
```bash
python -m src.cli.main process scenario_02_luxury_bumper_human_review.json
```
**Result:** ⏸ Paused, Requires Approval: Yes, ~€602

---

### 3. See what's waiting for approval
```bash
python -m src.cli.main queue
```
**Result:** Table showing all pending claims

---

### 4. Approve the claim
```bash
python -m src.cli.main approve CLM-2026-002 --reviewer YOUR_NAME
```
**Result:** ✓ Claim approved successfully

---

### 5. View the audit trail
```bash
python -m src.cli.main events CLM-2026-002
```
**Result:** Full event history for the claim

---

## What Just Happened?

1. **Scenario 1** - Low cost (€111) → Auto-approved instantly
2. **Scenario 2** - High cost (€602) → Paused for human review
3. **Queue** - Shows all claims waiting for decision
4. **Approve** - You made the decision, workflow resumed
5. **Events** - Complete audit trail of everything

---

## All Available Commands

```bash
python -m src.cli.main --help
```

| Command | Purpose |
|---------|---------|
| `process` | Run a claim through workflow |
| `queue` | View pending approvals |
| `approve` | Approve a claim |
| `reject` | Reject a claim |
| `status` | Check claim status |
| `events` | View audit trail |
| `stats` | Queue statistics |

---

## Want More Details?

See `CLI_WALKTHROUGH.md` for:
- Full explanations
- More scenarios
- Troubleshooting
- Practice exercises
