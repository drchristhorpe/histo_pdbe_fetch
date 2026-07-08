"""PDBe PISA assembly fetching and parsing.

The PDBe API serves assembly metadata as JSON files at:
https://www.ebi.ac.uk/pdbe/static/files/pisa/{pdb_id}/{pdb_id}-assembly{assembly_id}.json

Each assembly is fetched independently. Assembly ids are contiguous integers
starting at 1; discovery halts at the first 404 encountered.
"""

from __future__ import annotations

import json
from pathlib import Path

from histo_pdbe_fetch.http import DEFAULT_CACHE_DIR, cached_get

PDBE_PISA_URL_BASE = "https://www.ebi.ac.uk/pdbe/static/files/pisa"


def parse_assembly_json(json_text: str) -> dict | None:
    """Parse a PDBe PISA assembly JSON response.

    Returns the parsed assembly dict, or None if parsing fails.
    This is a pure function (no network, no I/O) — suitable for testing
    against committed fixtures.

    Args:
        json_text: Raw JSON response text from PDBe API

    Returns:
        Parsed dict (the full response), or None if parsing fails
    """
    try:
        data = json.loads(json_text)
        return data
    except json.JSONDecodeError:
        return None


def fetch_pdbe_assembly(
    pdb_id: str, assembly_id: int, cache_dir: Path = None, refresh: bool = False
) -> dict | None:
    """Fetch a specific assembly for a PDB id from PDBe.

    Args:
        pdb_id: 4-character PDB id (case-insensitive; lowercased for API)
        assembly_id: Assembly id (integer, typically 1, 2, 3, ...)
        cache_dir: Cache directory (defaults to ~/.cache/histo_pdbe_fetch)
        refresh: If True, bypass cache and re-fetch

    Returns:
        Parsed assembly dict, or None if the assembly doesn't exist (404)

    Raises:
        requests.HTTPError: On non-404 HTTP errors
        requests.RequestException: On network errors
    """
    if cache_dir is None:
        cache_dir = DEFAULT_CACHE_DIR

    pdb_id_lower = pdb_id.lower()
    url = f"{PDBE_PISA_URL_BASE}/{pdb_id_lower}/{pdb_id_lower}-assembly{assembly_id}.json"

    try:
        response_text = cached_get(url, cache_dir, refresh)
        return parse_assembly_json(response_text)
    except Exception as e:
        if "404" in str(e):
            return None
        raise
