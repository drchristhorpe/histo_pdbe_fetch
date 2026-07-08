"""Click CLI for histo-pdbe-fetch."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from histo_pdbe_fetch.core import PDBeFetcher
from histo_pdbe_fetch.http import DEFAULT_CACHE_DIR

console = Console()


@click.command()
@click.option(
    "--output",
    "-o",
    type=click.Path(file_okay=False, dir_okay=True),
    required=True,
    help="Output directory for assembled files",
)
@click.option(
    "--cache-dir",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    default=None,
    help="Cache directory for HTTP requests (default: ~/.cache/histo_pdbe_fetch)",
)
@click.option(
    "--refresh",
    is_flag=True,
    help="Bypass cache and re-fetch every assembly",
)
@click.argument("pdb_ids", nargs=-1, required=True)
def main(
    output: str, cache_dir: Path | None, refresh: bool, pdb_ids: tuple[str, ...]
) -> None:
    """Fetch biological unit assembly metadata from PDBe.

    Fetches all defined assemblies for each PDB_ID and writes them as:
    OUTPUT/{PDB_ID}/{pdb_id}__{assembly_id}.json

    Example:
        histo-pdbe-fetch --output ./structures 1ao7 1bak 2hla
    """
    fetcher = PDBeFetcher(cache_dir=cache_dir, refresh=refresh)

    try:
        result = fetcher.run(list(pdb_ids), output)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.ClickException(str(e))

    # Display results table
    table = Table(title="PDBe Assembly Fetch Summary")
    table.add_column("PDB ID", style="cyan")
    table.add_column("Assemblies", style="magenta")
    table.add_column("Status", style="green")

    for pdb_result in result["pdb_results"]:
        pdb_id = pdb_result["pdb_id"]
        count = pdb_result["assembly_count"]
        status = (
            "✓" if count > 0 else "✗ (not found)" if not pdb_result["errors"] else "✗ (error)"
        )
        table.add_row(pdb_id, str(count), status)

    console.print(table)
    console.print(
        f"\n[bold]Total:[/bold] {result['total_pdbs_processed']} PDBs, "
        f"{result['total_assemblies_written']} assemblies written to [cyan]{output}[/cyan]"
    )
    console.print(f"[dim]Cache:[/dim] {cache_dir or DEFAULT_CACHE_DIR}")


if __name__ == "__main__":
    main()
