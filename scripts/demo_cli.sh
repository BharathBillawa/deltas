#!/usr/bin/env bash
# Demo script for CLI commands

set -e

echo "================================"
echo "DELTAS CLI DEMO"
echo "================================"
echo ""

# Show version
echo "1. Show version"
echo "$ deltas version"
python -m src.cli.main version
echo ""

# Process a simple claim that auto-approves
echo "================================"
echo "2. Process auto-approve claim"
echo "$ deltas process scenario_01_minor_scratch_auto_approve.json"
python -m src.cli.main process scenario_01_minor_scratch_auto_approve.json
echo ""

# Process a claim that needs review
echo "================================"
echo "3. Process claim needing review"
echo "$ deltas process scenario_02_luxury_bumper_human_review.json"
python -m src.cli.main process scenario_02_luxury_bumper_human_review.json
echo ""

# Show approval queue
echo "================================"
echo "4. View approval queue"
echo "$ deltas queue"
python -m src.cli.main queue --limit 5
echo ""

# Show queue statistics
echo "================================"
echo "5. Queue statistics"
echo "$ deltas stats"
python -m src.cli.main stats
echo ""

# Check claim status
echo "================================"
echo "6. Check workflow status"
echo "$ deltas status CLM-2026-002"
python -m src.cli.main status CLM-2026-002 2>/dev/null || echo "(Claim may not exist)"
echo ""

# View events
echo "================================"
echo "7. View claim events"
echo "$ deltas events CLM-2026-001 --limit 5"
python -m src.cli.main events CLM-2026-001 --limit 5
echo ""

# Show help
echo "================================"
echo "8. Available commands"
echo "$ deltas --help"
python -m src.cli.main --help
echo ""

echo "================================"
echo "DEMO COMPLETE"
echo "================================"
echo ""
echo "To approve a claim:"
echo "  $ python -m src.cli.main approve CLM-2026-002 --reviewer YOUR_ID"
echo ""
echo "To reject a claim:"
echo "  $ python -m src.cli.main reject CLM-2026-003 --reason 'Insufficient evidence'"
