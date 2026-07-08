"""Public library API: fetch PDBe assemblies and write to folder hierarchy.

Each PDB gets its own folder; each assembly within that PDB is written as
{pdb_id_lowercase}__{assembly_id}.json.
"""

from __future__ import annotations

import json
from pathlib import Path

from histo_pdbe_fetch.http import DEFAULT_CACHE_DIR
from histo_pdbe_fetch.sources.pdbe import fetch_pdbe_assembly


class PDBeFetcher:
    """Fetches PDBe assembly metadata and organizes files by PDB and assembly id.

    `cache_dir` defaults to `~/.cache/histo_pdbe_fetch`; `refresh=True`
    bypasses the on-disk cache and re-fetches every assembly.
    """

    def __init__(self, cache_dir: Path | None = None, refresh: bool = False) -> None:
        self.cache_dir = cache_dir if cache_dir is not None else DEFAULT_CACHE_DIR
        self.refresh = refresh

    def run(self, pdb_ids: list[str], output_dir: str | Path) -> dict:
        """Fetch all assemblies for each PDB, write to output folder hierarchy.

        Args:
            pdb_ids: List of PDB ids to fetch (case-insensitive)
            output_dir: Output directory path (created if missing)

        Returns:
            Dict with per-PDB results:
            {
                "pdb_results": [
                    {
                        "pdb_id": "1AO7",
                        "assembly_count": 2,
                        "written_paths": ["output_dir/1AO7/1ao7__1.json", ...],
                        "errors": []
                    },
                    ...
                ],
                "total_assemblies_written": 5,
                "total_pdbs_processed": 3
            }
        """
        output_dir_path = Path(output_dir)
        output_dir_path.mkdir(parents=True, exist_ok=True)

        pdb_results = []
        total_assemblies = 0

        for pdb_id in pdb_ids:
            result = fetch_and_write_pdb_assemblies(
                pdb_id, output_dir_path, self.cache_dir, self.refresh
            )
            pdb_results.append(result)
            total_assemblies += result["assembly_count"]

        return {
            "pdb_results": pdb_results,
            "total_assemblies_written": total_assemblies,
            "total_pdbs_processed": len(pdb_ids),
        }


def fetch_and_write_pdb_assemblies(
    pdb_id: str, output_dir: Path, cache_dir: Path, refresh: bool
) -> dict:
    """Fetch all assemblies for one PDB, write each to output folder.

    Attempts to fetch assembly 1, 2, 3, ... until a 404 is encountered.

    Args:
        pdb_id: PDB id (case-insensitive)
        output_dir: Output directory (folder per PDB will be created here)
        cache_dir: Cache directory for HTTP requests
        refresh: If True, bypass cache

    Returns:
        Dict with "pdb_id", "assembly_count", "written_paths", "errors"
    """
    pdb_id_upper = pdb_id.upper()
    pdb_id_lower = pdb_id.lower()
    pdb_folder = output_dir / pdb_id_upper
    pdb_folder.mkdir(parents=True, exist_ok=True)

    written_paths = []
    errors = []
    assembly_id = 1

    while True:
        try:
            assembly_data = fetch_pdbe_assembly(pdb_id, assembly_id, cache_dir, refresh)
            if assembly_data is None:
                break

            output_file = pdb_folder / f"{pdb_id_lower}__{assembly_id}.json"
            output_file.write_text(
                json.dumps(assembly_data, indent=2, sort_keys=False) + "\n",
                encoding="utf-8",
            )
            written_paths.append(str(output_file))
            assembly_id += 1
        except Exception as e:
            errors.append({"assembly_id": assembly_id, "error": str(e)})
            break

    return {
        "pdb_id": pdb_id_upper,
        "assembly_count": len(written_paths),
        "written_paths": written_paths,
        "errors": errors,
    }
