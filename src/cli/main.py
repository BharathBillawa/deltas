"""CLI entry point for the Deltas application."""

import json
import logging
import warnings
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from typing_extensions import Annotated

from src.models.damage import DamageClaim, DamageAssessment, DamageType, DamageSeverity, VehicleLocation
from src.graph.workflow import DamageClaimWorkflow
from src.persistence.database import SessionLocal
from src.services.event_logger import EventLogger

# Configure cleaner logging for CLI
# Show WARNING and above (includes errors), hide INFO/DEBUG
logging.basicConfig(
    level=logging.WARNING,
    format="%(message)s"
)

# Reduce noise from specific loggers
logging.getLogger("langgraph.checkpoint.base").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)

# Note: LangGraph checkpoint warnings print to stderr directly (not via logging)
# These are informational warnings about serialization and can be safely ignored
# They don't affect functionality and will be addressed in future LangGraph versions

app = typer.Typer(
    name="deltas",
    help="AI-powered damage claims automation system",
    no_args_is_help=True,
)

console = Console()


@app.command()
def version():
    """Show version information."""
    console.print("[bold blue]Deltas v0.1.0[/bold blue]")
    console.print("AI-powered damage claims automation")


@app.command()
def process(
    scenario: Annotated[str, typer.Argument(help="Scenario file path or claim_id")],
    wait: Annotated[bool, typer.Option("--wait", "-w", help="Wait if needs human review")] = False,
):
    """
    Process a damage claim through the workflow.

    Examples:
        deltas process scenario_01_minor_scratch_auto_approve.json
        deltas process CLM-2026-001
        deltas process scenarios/my_claim.json --wait
    """
    try:
        console.print(f"[bold]Processing claim from:[/bold] {scenario}")

        # Load claim from scenario
        claim = _load_claim_from_scenario(scenario)

        if not claim:
            console.print("[red]✗[/red] Failed to load claim")
            raise typer.Exit(1)

        console.print(f"[green]✓[/green] Loaded claim: {claim.claim_id}")
        console.print(f"  Vehicle: {claim.vehicle_id}")
        console.print(f"  Customer: {claim.customer_id}")
        console.print(
            f"  Damage: {claim.damage_assessment.damage_type.value} "
            f"({claim.damage_assessment.severity.value})"
        )

        # Process through workflow
        workflow = DamageClaimWorkflow(use_checkpointer=True)

        with console.status("[bold green]Processing workflow...", spinner="dots"):
            result = workflow.process_claim(claim)

        # Display result
        console.print()
        _display_workflow_result(result)

        # Check if waiting for approval
        if result.requires_human_approval and not result.workflow_complete:
            if wait:
                console.print(
                    "\n[yellow]Claim requires human review. "
                    "Use 'deltas approve' or 'deltas reject' to continue.[/yellow]"
                )
            else:
                console.print("\n[yellow]⏸  Workflow paused - awaiting approval[/yellow]")
                console.print(f"Use: [bold]deltas approve {claim.claim_id}[/bold] to approve")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def queue(
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max items to show")] = 20,
):
    """List claims in approval queue."""
    try:
        workflow = DamageClaimWorkflow(use_checkpointer=True)
        pending = workflow.get_pending_approvals()

        if not pending:
            console.print("[yellow]No claims pending approval[/yellow]")
            return

        # Create table
        table = Table(title=f"Approval Queue ({len(pending)} items)")
        table.add_column("Claim ID", style="cyan", no_wrap=True)
        table.add_column("Vehicle", style="magenta")
        table.add_column("Cost", justify="right", style="green")
        table.add_column("Reason", style="yellow")
        table.add_column("Priority", justify="center")
        table.add_column("Added", style="dim")

        for item in pending[:limit]:
            table.add_row(
                item["claim_id"],
                item["vehicle_id"],
                f"€{item['estimated_cost_eur']:.2f}",
                item["escalation_reason"][:40],
                str(item["priority"]),
                item["timestamp_added"][:19] if item["timestamp_added"] else "N/A"
            )

        console.print(table)

        if len(pending) > limit:
            console.print(f"\n[dim]Showing {limit} of {len(pending)} items. Use --limit to see more.[/dim]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def approve(
    claim_id: Annotated[str, typer.Argument(help="Claim ID to approve")],
    reviewer: Annotated[str, typer.Option("--reviewer", "-r", help="Reviewer ID")] = "CLI_USER",
    notes: Annotated[Optional[str], typer.Option("--notes", "-n", help="Approval notes")] = None,
):
    """Approve a pending claim and resume workflow."""
    try:
        workflow = DamageClaimWorkflow(use_checkpointer=True)

        # Check if claim is awaiting approval
        if not workflow.is_awaiting_approval(claim_id):
            console.print(f"[yellow]Warning:[/yellow] Claim {claim_id} is not awaiting approval")

            # Show if it exists in queue
            status = workflow.get_status(claim_id)
            if status:
                console.print(f"Status: workflow_complete={status.get('workflow_complete')}")
            else:
                console.print("Claim not found in workflow state")
            raise typer.Exit(1)

        console.print(f"[bold]Approving claim:[/bold] {claim_id}")
        console.print(f"Reviewer: {reviewer}")
        if notes:
            console.print(f"Notes: {notes}")

        # Resume workflow with approval
        with console.status("[bold green]Resuming workflow...", spinner="dots"):
            result = workflow.resume_after_approval(
                claim_id=claim_id,
                approved=True,
                reviewer_id=reviewer,
                notes=notes
            )

        console.print("\n[green]✓[/green] Claim approved successfully")
        console.print(f"Workflow complete: {result.workflow_complete}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def reject(
    claim_id: Annotated[str, typer.Argument(help="Claim ID to reject")],
    reason: Annotated[str, typer.Option("--reason", "-r", help="Rejection reason", prompt=True)],
    reviewer: Annotated[str, typer.Option("--reviewer", help="Reviewer ID")] = "CLI_USER",
):
    """Reject a pending claim."""
    try:
        workflow = DamageClaimWorkflow(use_checkpointer=True)

        if not workflow.is_awaiting_approval(claim_id):
            console.print(f"[yellow]Warning:[/yellow] Claim {claim_id} is not awaiting approval")
            raise typer.Exit(1)

        console.print(f"[bold]Rejecting claim:[/bold] {claim_id}")
        console.print(f"Reviewer: {reviewer}")
        console.print(f"Reason: {reason}")

        # Resume workflow with rejection
        with console.status("[bold red]Rejecting claim...", spinner="dots"):
            result = workflow.resume_after_approval(
                claim_id=claim_id,
                approved=False,
                reviewer_id=reviewer,
                notes=reason
            )

        console.print("\n[red]✗[/red] Claim rejected")
        console.print(f"Workflow complete: {result.workflow_complete}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def status(
    claim_id: Annotated[str, typer.Argument(help="Claim ID to check")],
):
    """Check workflow status for a claim."""
    try:
        workflow = DamageClaimWorkflow(use_checkpointer=True)
        status = workflow.get_status(claim_id)

        if not status:
            console.print(f"[yellow]No workflow state found for claim:[/yellow] {claim_id}")
            raise typer.Exit(1)

        # Display status
        table = Table(title=f"Workflow Status: {claim_id}")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Workflow Complete", "✓" if status["workflow_complete"] else "✗")
        table.add_row("Requires Approval", "Yes" if status["requires_human_approval"] else "No")

        if status.get("approval_granted") is not None:
            table.add_row("Approved", "✓" if status["approval_granted"] else "✗")

        table.add_row("Next Step", status.get("next_step", "N/A"))

        if status.get("is_paused"):
            table.add_row("Paused At", ", ".join(status.get("paused_at", [])))

        if status.get("errors"):
            table.add_row("Errors", str(len(status["errors"])))

        console.print(table)

        # Show cost estimate if available
        if status.get("cost_estimate"):
            cost = status["cost_estimate"]
            console.print(f"\n[bold]Cost Estimate:[/bold] €{cost.get('total_eur', 0):.2f}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def events(
    claim_id: Annotated[str, typer.Argument(help="Claim ID")],
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max events to show")] = 50,
):
    """View events for a claim."""
    try:
        db = SessionLocal()
        try:
            event_logger = EventLogger(db)
            claim_events = event_logger.get_events_for_claim(claim_id)

            if not claim_events:
                console.print(f"[yellow]No events found for claim:[/yellow] {claim_id}")
                return

            # Create table
            table = Table(title=f"Events for {claim_id} ({len(claim_events)} total)")
            table.add_column("#", style="dim", width=4)
            table.add_column("Type", style="cyan")
            table.add_column("Timestamp", style="magenta")
            table.add_column("Priority", justify="center")
            table.add_column("Details", style="dim")

            for i, event in enumerate(claim_events[:limit], 1):
                # Format data for display
                data = event.get("data", {})
                details = ", ".join(f"{k}={v}" for k, v in list(data.items())[:2])

                table.add_row(
                    str(i),
                    event["event_type"],
                    event["timestamp"][:19],
                    event.get("priority", "normal"),
                    details[:50]
                )

            console.print(table)

            if len(claim_events) > limit:
                console.print(f"\n[dim]Showing {limit} of {len(claim_events)} events. Use --limit to see more.[/dim]")

        finally:
            db.close()

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def stats():
    """Show approval queue statistics."""
    try:
        from src.services.approval_service import ApprovalService

        db = SessionLocal()
        try:
            approval_service = ApprovalService(db)
            stats = approval_service.get_queue_stats()

            # Display stats
            table = Table(title="Queue Statistics")
            table.add_column("Metric", style="cyan")
            table.add_column("Count", justify="right", style="green")

            table.add_row("Pending Review", str(stats["pending"]))
            table.add_row("Approved", str(stats["approved"]))
            table.add_row("Rejected", str(stats["rejected"]))
            table.add_row("Escalated", str(stats["escalated"]))
            table.add_row("Total", str(stats["total"]))
            table.add_row("", "")
            table.add_row("Avg Review Time (hours)", f"{stats['avg_hours_to_review']:.1f}")

            console.print(table)

        finally:
            db.close()

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


# Helper functions

def _load_claim_from_scenario(scenario_path: str) -> Optional[DamageClaim]:
    """Load a claim from scenario file or by claim_id."""
    # Try direct file path
    path = Path(scenario_path)
    if path.exists():
        return _parse_scenario_file(path)

    # Try in scenarios directory
    scenarios_dir = Path(__file__).parent.parent.parent / "data" / "sample_scenarios"

    # Try with .json extension
    if not scenario_path.endswith(".json"):
        scenario_file = scenarios_dir / f"{scenario_path}.json"
        if scenario_file.exists():
            return _parse_scenario_file(scenario_file)

    # Try exact filename in scenarios dir
    scenario_file = scenarios_dir / scenario_path
    if scenario_file.exists():
        return _parse_scenario_file(scenario_file)

    # Search by claim_id
    for scenario_file in scenarios_dir.glob("*.json"):
        try:
            with open(scenario_file) as f:
                data = json.load(f)
                if data.get("damage_claim", {}).get("claim_id") == scenario_path:
                    return _parse_scenario_file(scenario_file)
        except (json.JSONDecodeError, KeyError, IOError):
            continue

    return None


def _parse_scenario_file(path: Path) -> DamageClaim:
    """Parse scenario JSON file into DamageClaim."""
    with open(path) as f:
        data = json.load(f)

    claim_data = data["damage_claim"]
    assessment = claim_data["damage_assessment"]

    return DamageClaim(
        claim_id=claim_data["claim_id"],
        timestamp=datetime.fromisoformat(claim_data["timestamp"].replace("Z", "+00:00")),
        vehicle_id=claim_data["vehicle_id"],
        customer_id=claim_data["customer_id"],
        rental_agreement_id=claim_data["rental_agreement_id"],
        return_location=claim_data["return_location"],
        damage_assessment=DamageAssessment(
            damage_type=DamageType(assessment["damage_type"]),
            severity=DamageSeverity(assessment["severity"]),
            location=VehicleLocation(assessment["location"]),
            description=assessment["description"],
            affected_parts=assessment["affected_parts"],
            photos=assessment.get("photos", []),
            inspector_id=assessment.get("inspector_id", "CLI_USER"),
            inspector_notes=assessment.get("inspector_notes")
        )
    )


def _display_workflow_result(result):
    """Display workflow result in a nice format."""
    # Check if AI was used
    ai_cost_used = hasattr(result, 'ai_cost_reasoning') and result.ai_cost_reasoning
    ai_validation_used = hasattr(result, 'ai_validation_reasoning') and result.ai_validation_reasoning

    table = Table(title="Workflow Result")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")

    # Status
    status_icon = "✓" if result.workflow_complete else "⏸"
    table.add_row("Status", f"{status_icon} {'Complete' if result.workflow_complete else 'Paused'}")

    # Decision mode indicator
    if ai_cost_used or ai_validation_used:
        modes = []
        if ai_cost_used:
            modes.append("Cost")
        if ai_validation_used:
            modes.append("Validation")
        table.add_row("Decision Mode", f"🤖 AI-Powered ({', '.join(modes)})")
    else:
        table.add_row("Decision Mode", "📋 Rule-Based")

    # Approval status
    if result.approval_granted is not None:
        approval_icon = "✓" if result.approval_granted else "✗"
        table.add_row("Approved", f"{approval_icon} {'Yes' if result.approval_granted else 'No'}")
    elif result.requires_human_approval:
        table.add_row("Requires Approval", "Yes")

    # Cost estimate
    if result.cost_estimate:
        cost = result.cost_estimate.total_eur
        table.add_row("Estimated Cost", f"€{cost:.2f}")

        if result.cost_estimate.depreciation_applicable:
            table.add_row("Depreciation", f"{result.cost_estimate.depreciation_factor:.0%}")

    # Validation
    if result.validation_result:
        table.add_row("Routing Decision", result.validation_result.routing_decision.value)

        if result.validation_result.flags:
            flags = [f.flag_type for f in result.validation_result.flags]
            table.add_row("Flags", ", ".join(flags[:3]))

    console.print(table)

    # Show AI reasoning if available
    ai_cost_used = hasattr(result, 'ai_cost_reasoning') and result.ai_cost_reasoning
    ai_validation_used = hasattr(result, 'ai_validation_reasoning') and result.ai_validation_reasoning

    if ai_cost_used:
        console.print("\n[bold cyan]🤖 AI Cost Analysis:[/bold cyan]")
        console.print(f"[dim]{result.ai_cost_reasoning}[/dim]")

    if ai_validation_used:
        console.print("\n[bold cyan]🤖 AI Validation Analysis:[/bold cyan]")
        console.print(f"[dim]{result.ai_validation_reasoning}[/dim]")

    # Show decision mode explanation if no AI was used
    if not ai_cost_used and not ai_validation_used:
        console.print("\n[dim]💡 Rule-based decision: No edge cases detected, using deterministic logic[/dim]")


if __name__ == "__main__":
    app()
