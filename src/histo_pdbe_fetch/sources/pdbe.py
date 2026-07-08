"""PDBe assembly discovery and structure file fetching.

Assembly discovery: PDBe API provides list of available biological unit assemblies:
  https://www.ebi.ac.uk/pdbe/api/v2/pdb/entry/assembly/{pdb_id}

Structure files: PDBe provides biological unit assemblies in mmCIF format (gzipped):
  https://www.ebi.ac.uk/pdbe/static/entry/download/{pdb_id}-assembly{assembly_id}.cif.gz

BioPython converts CIF to PDB format locally, with automatic chain ID remapping
for extended chain IDs (e.g., "A-1", "A-2") that exceed PDB's single-char limit.
"""

from __future__ import annotations

import gzip
import json
from io import StringIO
from pathlib import Path

from histo_pdbe_fetch.chain_remapper import cif_to_pdb_with_remapping
from histo_pdbe_fetch.http import DEFAULT_CACHE_DIR, cached_get

PDBE_ASSEMBLY_API_BASE = "https://www.ebi.ac.uk/pdbe/api/v2/pdb/entry/assembly"
PDBE_DOWNLOAD_BASE = "https://www.ebi.ac.uk/pdbe/static/entry/download"


def discover_assemblies(pdb_id: str, cache_dir: Path = None, refresh: bool = False) -> list[str]:
    """Discover all biological unit assembly IDs for a PDB entry.

    Args:
        pdb_id: 4-character PDB id (case-insensitive)
        cache_dir: Cache directory (defaults to ~/.cache/histo_pdbe_fetch)
        refresh: If True, bypass cache and re-fetch

    Returns:
        List of assembly IDs as strings (e.g., ["1", "2", "3"]), sorted numerically.
        Returns empty list if PDB not found or no assemblies.

    Raises:
        requests.HTTPError: On non-404 HTTP errors
        requests.RequestException: On network errors
        json.JSONDecodeError: On invalid JSON response
    """
    if cache_dir is None:
        cache_dir = DEFAULT_CACHE_DIR

    pdb_id_lower = pdb_id.lower()
    url = f"{PDBE_ASSEMBLY_API_BASE}/{pdb_id_lower}"

    try:
        response_text = cached_get(url, cache_dir, refresh)
        data = json.loads(response_text)

        # Extract assembly IDs from response
        # Response format: {pdb_id: [{assembly_id: "1", ...}, {assembly_id: "2", ...}]}
        pdb_key = pdb_id_lower
        if pdb_key in data:
            assembly_list = data[pdb_key]
            assembly_ids = [str(asm.get("assembly_id", "")) for asm in assembly_list if "assembly_id" in asm]
            # Sort numerically
            return sorted(assembly_ids, key=lambda x: int(x) if x.isdigit() else float("inf"))
        return []
    except Exception as e:
        if "404" in str(e):
            return []
        raise


def fetch_cif_file(
    pdb_id: str, assembly_id: str, cache_dir: Path = None, refresh: bool = False
) -> str | None:
    """Download and decompress a biological unit assembly CIF file from PDBe.

    Args:
        pdb_id: 4-character PDB id (case-insensitive)
        assembly_id: Assembly ID as string (e.g., "1", "2")
        cache_dir: Cache directory (defaults to ~/.cache/histo_pdbe_fetch)
        refresh: If True, bypass cache and re-fetch

    Returns:
        Decompressed CIF file content as string, or None if not found

    Raises:
        requests.HTTPError: On HTTP errors
        requests.RequestException: On network errors
        gzip.BadGzipFile: On corrupted gzip data
    """
    if cache_dir is None:
        cache_dir = DEFAULT_CACHE_DIR

    pdb_id_lower = pdb_id.lower()
    url = f"{PDBE_DOWNLOAD_BASE}/{pdb_id_lower}-assembly{assembly_id}.cif.gz"

    try:
        # cached_get returns raw content for gzipped files
        # We need to handle it as binary, so we'll fetch differently
        import requests

        # Check cache first
        cache_file = _cache_path_binary(cache_dir, url)
        if not refresh and cache_file.exists():
            return _decompress_gzip(cache_file.read_bytes())

        # Fetch from URL
        response = requests.get(
            url,
            headers={"User-Agent": "histo-pdbe-fetch/0.1.0"},
            timeout=30,
        )
        response.raise_for_status()

        # Cache the gzipped content
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_bytes(response.content)

        # Decompress and return
        return _decompress_gzip(response.content)
    except Exception as e:
        if "404" in str(e):
            return None
        raise


def cif_to_pdb(cif_content: str, pdb_id: str) -> str:
    """Convert CIF format structure to PDB format using BioPython.

    Automatically remaps extended chain IDs (e.g., "A-1", "A-2") to PDB format
    (A-Z, then 0-9). Documents remapping in PDB REMARK lines.

    Args:
        cif_content: CIF file content as string
        pdb_id: PDB ID for the structure (used in HEADER line)

    Returns:
        PDB format content as string

    Raises:
        ValueError: If more than 36 unique chains
        Bio.PDB.PDBExceptions: On parsing errors
    """
    pdb_content, _ = cif_to_pdb_with_remapping(cif_content, pdb_id, allow_remapping=True)
    return pdb_content


# Helper functions
import hashlib


def _cache_path_binary(cache_dir: Path, url: str) -> Path:
    """Derive a cache file path from URL via SHA256 hash."""
    url_hash = hashlib.sha256(url.encode()).hexdigest()
    return cache_dir / url_hash


def _decompress_gzip(gzipped_bytes: bytes) -> str:
    """Decompress gzipped bytes and return as string."""
    return gzip.decompress(gzipped_bytes).decode("utf-8")
