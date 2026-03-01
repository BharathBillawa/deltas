# CLI Hands-On Walkthrough

This guide walks you through testing the CLI with real scenarios.

## Setup

All commands should be run from the project root:
```bash
cd /Users/BPOOJAR/CodeZ/test_track/deltas
```

## Scenario 1: Simple Auto-Approve Claim

**What it is:** Minor scratch that gets automatically approved (under €500)

### Step 1: Process the claim
```bash
python -m src.cli.main process scenario_01_minor_scratch_auto_approve.json
```

**What to look for:**
- ✓ Status: Complete
- ✓ Approved: Yes
- Cost around €111 (with 70% depreciation)
- Routing Decision: auto_approve

### Step 2: Check the claim's events
```bash
python -m src.cli.main events CLM-2026-001
```

**What you'll see:**
- ClaimReceived
- CostEstimated
- ClaimApproved
- Full audit trail

---

## Scenario 2: Human Review Required (The Full Workflow)

**What it is:** Luxury vehicle bumper crack that costs €602, requires approval

### Step 1: Process the claim
```bash
python -m src.cli.main process scenario_02_luxury_bumper_human_review.json
```

**What to look for:**
- ⏸ Status: Paused
- Requires Approval: Yes
- Cost: €602.66
- Message: "Use: deltas approve CLM-2026-002 to approve"

### Step 2: View the approval queue
```bash
python -m src.cli.main queue
```

**What you'll see:**
- CLM-2026-002 in the queue
- Cost: €602.66
- Reason: high_cost
- Priority: 3

### Step 3: Check the claim status
```bash
python -m src.cli.main status CLM-2026-002
```

**What you'll see:**
- Workflow Complete: ✗
- Requires Approval: Yes
- Next Step: awaiting_approval
- Paused At: human_review

### Step 4: Approve the claim
```bash
python -m src.cli.main approve CLM-2026-002 --reviewer YOUR_NAME
```

**Optional: Add notes**
```bash
python -m src.cli.main approve CLM-2026-002 --reviewer YOUR_NAME --notes "Cost is reasonable for luxury vehicle"
```

**What happens:**
- Workflow resumes from where it paused
- Claim gets approved
- Events logged
- Approval queue updated

### Step 5: Check events to see the full history
```bash
python -m src.cli.main events CLM-2026-002
```

**What you'll see:**
- ClaimReceived
- CostEstimated
- ApprovalRequired
- ClaimApproved (with your reviewer ID)

---

## Scenario 3: Pattern Detection

**What it is:** Vehicle with multiple previous damages, triggers pattern detection

### Try it yourself:
```bash
python -m src.cli.main process scenario_03_pattern_detection_frequent_damage.json
```

**What to observe:**
- Status: Paused (needs review)
- Routing Reason: "Multiple patterns detected"
- Flags include pattern detection warnings
- Lower cost (€100) but still needs review due to patterns

---

## Practice Commands

### View queue statistics
```bash
python -m src.cli.main stats
```

Shows:
- How many claims pending review
- How many approved/rejected
- Average review time

### List all pending claims
```bash
python -m src.cli.main queue
```

See all claims waiting for approval, sorted by priority.

### Reject a claim
```bash
python -m src.cli.main reject CLM-2026-003 --reason "Insufficient documentation"
```

The CLI will prompt you for the reason if you don't provide it.

---

## Quick Reference

| Command | What it does |
|---------|--------------|
| `process <scenario>` | Run a claim through the workflow |
| `queue` | See what's awaiting approval |
| `status <claim_id>` | Check where a claim is in the workflow |
| `approve <claim_id>` | Approve and resume workflow |
| `reject <claim_id>` | Reject a claim |
| `events <claim_id>` | See full history/audit trail |
| `stats` | Queue statistics |
| `version` | Show version info |

---

## Exercise: Complete Workflow

Try this sequence to see the full human-in-the-loop workflow:

1. **Process a claim that needs review:**
   ```bash
   python -m src.cli.main process scenario_02_luxury_bumper_human_review.json
   ```

2. **Check what's in the queue:**
   ```bash
   python -m src.cli.main queue
   ```

3. **Look at the claim details:**
   ```bash
   python -m src.cli.main status CLM-2026-002
   ```

4. **Make a decision - either approve:**
   ```bash
   python -m src.cli.main approve CLM-2026-002 --reviewer DEMO_USER
   ```

5. **Or reject:**
   ```bash
   python -m src.cli.main reject CLM-2026-002 --reason "Cost too high"
   ```

6. **View the audit trail:**
   ```bash
   python -m src.cli.main events CLM-2026-002
   ```

---

## Troubleshooting

### "Claim not awaiting approval"
- The claim might have already been processed
- Or it auto-approved (under €500 threshold)
- Check with: `python -m src.cli.main status <claim_id>`

### "No workflow state found"
- You need to process the claim first
- Use: `python -m src.cli.main process <scenario>`

### See all available scenarios
```bash
ls data/sample_scenarios/
```

---

## Understanding the Output

### Auto-Approved Claims
```
Status: ✓ Complete
Approved: ✓ Yes
```
→ Went straight through, no human needed

### Claims Needing Review
```
Status: ⏸ Paused
Requires Approval: Yes
```
→ Workflow stopped, waiting for your decision

### After You Approve
```
Workflow complete: True
```
→ Process finished, claim fully processed
