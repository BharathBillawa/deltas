"""CLI entry point for the Deltas application."""

import typer
from typing_extensions import Annotated

app = typer.Typer(
    name="deltas",
    help="AI-powered damage claims automation system",
    no_args_is_help=True,
)


@app.command()
def version():
    """Show version information."""
    typer.echo("Deltas v0.1.0")
    typer.echo("AI-powered damage claims automation")


@app.command()
def process(
    claim_id: Annotated[str, typer.Option("--claim-id", "-c", help="Claim ID to process")],
):
    """Process a damage claim."""
    typer.echo(f"Processing claim: {claim_id}")
    typer.echo("⚠️  Not yet implemented - coming soon!")


@app.command()
def queue(
    status: Annotated[
        str, typer.Option("--status", "-s", help="Filter by status")
    ] = "pending",
):
    """List claims in approval queue."""
    typer.echo(f"Listing claims with status: {status}")
    typer.echo("⚠️  Not yet implemented - coming soon!")


@app.command()
def approve(
    claim_id: Annotated[str, typer.Option("--claim-id", "-c", help="Claim ID to approve")],
):
    """Approve a pending claim."""
    typer.echo(f"Approving claim: {claim_id}")
    typer.echo("⚠️  Not yet implemented - coming soon!")


if __name__ == "__main__":
    app()
