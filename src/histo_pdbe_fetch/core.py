"""Public library API: fetch PDBe assemblies and write to folder hierarchy.

Each PDB gets its own folder; each assembly within that PDB is written as
{pdb_id_lowercase}__{assembly_id}.cif and {pdb_id_lowercase}__{assembly_id}.pdb.
"""

from __future__ import annotations

from pathlib import Path

from histo_pdbe_fetch.http import DEFAULT_CACHE_DIR
from histo_pdbe_fetch.sources.pdbe import cif_to_pdb, discover_assemblies, fetch_cif_file


class PDBeFetcher:
    """Fetches PDBe biological unit assembly structures and organizes files by PDB and assembly id.

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
                        "pdb_id": "1ao7",
                        "assembly_count": 2,
                        "written_paths": ["output_dir/1ao7/1ao7__1.cif", ...],
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
    """Fetch all assemblies for one PDB, write CIF and PDB files to output folder.

    Args:
        pdb_id: PDB id (case-insensitive; lowercased internally)
        output_dir: Output directory (folder per PDB will be created here)
        cache_dir: Cache directory for HTTP requests
        refresh: If True, bypass cache

    Returns:
        Dict with "pdb_id" (lowercase), "assembly_count", "written_paths", "errors"
    """
    pdb_id_lower = pdb_id.lower()
    pdb_folder = output_dir / pdb_id_lower
    pdb_folder.mkdir(parents=True, exist_ok=True)

    written_paths = []
    errors = []
    assembly_count = 0

    try:
        # Discover all available assemblies
        assembly_ids = discover_assemblies(pdb_id, cache_dir, refresh)

        if not assembly_ids:
            errors.append({"error": "No assemblies found or PDB not found"})
            return {
                "pdb_id": pdb_id_lower,
                "assembly_count": 0,
                "written_paths": [],
                "errors": errors,
            }

        # Fetch and write each assembly
        for assembly_id in assembly_ids:
            try:
                base_filename = f"{pdb_id_lower}__{assembly_id}"

                # Download and decompress CIF file
                cif_content = fetch_cif_file(pdb_id, assembly_id, cache_dir, refresh)
                if not cif_content:
                    errors.append({"assembly_id": assembly_id, "error": "CIF file not found"})
                    continue

                # Write CIF file
                cif_file = pdb_folder / f"{base_filename}.cif"
                cif_file.write_text(cif_content, encoding="utf-8")
                written_paths.append(str(cif_file))

                # Convert CIF to PDB using BioPython
                try:
                    pdb_content = cif_to_pdb(cif_content, pdb_id.upper())
                    pdb_file = pdb_folder / f"{base_filename}.pdb"
                    pdb_file.write_text(pdb_content, encoding="utf-8")
                    written_paths.append(str(pdb_file))
                except Exception as e:
                    errors.append(
                        {"assembly_id": assembly_id, "error": f"CIF to PDB conversion failed: {str(e)}"}
                    )

                assembly_count += 1
            except Exception as e:
                errors.append({"assembly_id": assembly_id, "error": str(e)})

    except Exception as e:
        errors.append({"error": f"Assembly discovery failed: {str(e)}"})

    return {
        "pdb_id": pdb_id_lower,
        "assembly_count": assembly_count,
        "written_paths": written_paths,
        "errors": errors,
    }
