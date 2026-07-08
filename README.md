# histo-pdbe-fetch

Fetch biological unit assembly structures from the PDBe (Protein Data Bank in Europe).

Downloads all available biological unit assemblies for one or more PDB codes in both mmCIF and PDB formats, with automatic chain ID remapping for extended identifiers that exceed PDB format limits.

## Installation

```bash
git clone https://github.com/drchristhorpe/histo_pdbe_fetch.git
cd histo_pdbe_fetch
uv pip install -e .
```

Requires Python 3.11+.

## Quick Start

### Command-line usage

```bash
histo-pdbe-fetch --output ./structures 1ao7 1hhk
```

Creates:
```
structures/
  1ao7/
    1ao7__1.cif      # mmCIF format
    1ao7__1.pdb      # PDB format (converted from CIF)
    1ao7__2.cif
    1ao7__2.pdb
  1hhk/
    1hhk__1.cif
    1hhk__1.pdb
    1hhk__2.cif
    1hhk__2.pdb
```

### Python library usage

```python
from histo_pdbe_fetch import PDBeFetcher

fetcher = PDBeFetcher(cache_dir=None, refresh=False)
result = fetcher.run(pdb_ids=["1ao7", "1hhk"], output_dir="./structures/")

print(f"Processed {result['total_pdbs_processed']} PDBs")
print(f"Downloaded {result['total_assemblies_written']} assemblies")
```

## Features

### Automatic assembly discovery
Queries the PDBe API to find all biological unit assemblies for each PDB code. No manual assembly ID specification needed.

### Efficient caching
HTTP responses cached on disk by URL hash (default: `~/.cache/histo_pdbe_fetch/`). Use `--refresh` to bypass cache.

### Automatic chain ID remapping
Some biological unit assemblies have extended chain identifiers (e.g., "A-1", "B-2") exceeding PDB format's single-character limit. The tool automatically remaps these to A-Z, then 0-9, documenting the mapping in PDB REMARK lines:

```
REMARK   1 CHAIN ID REMAPPING FOR PDB FORMAT COMPATIBILITY
REMARK   1 CHAIN A-1 REMAPPED TO A
REMARK   1 CHAIN B-2 REMAPPED TO C
```

Original chain IDs can be recovered from the REMARK documentation if needed.

### Both file formats
Provides both mmCIF (from PDBe) and PDB format (converted via BioPython) for each assembly. Useful for tools that prefer one format over the other.

## CLI Reference

```
histo-pdbe-fetch --output DIR [--cache-dir DIR] [--refresh] PDB_ID [PDB_ID ...]
```

**Options:**
- `--output DIR` (required): Output directory (created if missing)
- `--cache-dir DIR` (optional): Cache directory (default: `~/.cache/histo_pdbe_fetch/`)
- `--refresh` (flag): Bypass cache and re-fetch all assemblies
- `PDB_ID` (positional, one or more): 4-character PDB codes (case-insensitive)

**Output on completion:**
- Rich console summary showing PDBs processed, assemblies downloaded, cache location, output directory

## Library API

```python
from histo_pdbe_fetch import (
    PDBeFetcher,
    discover_assemblies,
    fetch_cif_file,
    cif_to_pdb,
    cif_to_pdb_with_remapping
)
```

### High-level API: `PDBeFetcher`

```python
fetcher = PDBeFetcher(cache_dir=None, refresh=False)
result = fetcher.run(pdb_ids=["1ao7"], output_dir="./structures/")
```

**Returns:**
```python
{
  "pdb_results": [
    {
      "pdb_id": "1ao7",
      "assembly_count": 2,
      "written_paths": ["./structures/1ao7/1ao7__1.cif", ...],
      "errors": []
    }
  ],
  "total_assemblies_written": 2,
  "total_pdbs_processed": 1
}
```

### Low-level functions for custom workflows

**Discover assemblies:**
```python
assembly_ids = discover_assemblies("1ao7", cache_dir=cache_dir, refresh=False)
# Returns: ["1", "2", "3"]
```

**Fetch CIF file:**
```python
cif_content = fetch_cif_file("1ao7", "1", cache_dir=cache_dir, refresh=False)
# Returns: decompressed CIF file content as string
```

**Convert CIF to PDB:**
```python
pdb_content = cif_to_pdb(cif_content, "1AO7")
# Returns: PDB format content with chain remapping applied automatically

# Or get both PDB and mapping dict:
pdb_content, chain_mapping = cif_to_pdb_with_remapping(cif_content, "1AO7")
# chain_mapping: {"A-1": "A", "B-2": "C", ...}
```

## Data sources

- **Assembly discovery**: PDBe API v2
  - Endpoint: `https://www.ebi.ac.uk/pdbe/api/v2/pdb/entry/assembly/{pdb_id}`
  - Returns list of available assembly IDs in JSON format

- **Structure files**: PDBe static download
  - Endpoint: `https://www.ebi.ac.uk/pdbe/static/entry/download/{pdb_id}-assembly{assembly_id}.cif.gz`
  - Files are gzipped mmCIF format, automatically decompressed

## File formats

### mmCIF (Crystallographic Information File)
Raw format from PDBe. Contains all structural information including extended chain IDs.

### PDB (Protein Data Bank)
Generated from mmCIF via BioPython. Chain IDs remapped to single characters (A-Z, 0-9) if needed, with mapping documented in REMARK lines.

## Examples

### Fetch assemblies for multiple PDBs
```bash
histo-pdbe-fetch --output ./pdb_data 1ao7 1hhk 2hla
```

### Use custom cache directory
```bash
histo-pdbe-fetch --output ./structures --cache-dir /tmp/pdb_cache 1ao7
```

### Bypass cache and re-fetch
```bash
histo-pdbe-fetch --output ./structures --refresh 1ao7
```

### Python: Fetch and inspect chain mapping
```python
from histo_pdbe_fetch import discover_assemblies, fetch_cif_file, cif_to_pdb_with_remapping
from pathlib import Path

cache_dir = Path.home() / ".cache" / "histo_pdbe_fetch"

# Discover assemblies
assemblies = discover_assemblies("1ao7", cache_dir=cache_dir)
print(f"Found {len(assemblies)} assemblies: {assemblies}")

# Fetch and convert with mapping info
cif_content = fetch_cif_file("1ao7", "2", cache_dir=cache_dir)
pdb_content, chain_mapping = cif_to_pdb_with_remapping(cif_content, "1AO7")

# Print original → remapped chain IDs
if chain_mapping:
    print("Chain ID remapping applied:")
    for orig, new in sorted(chain_mapping.items()):
        print(f"  {orig} → {new}")
```

## Error handling

Errors are reported per assembly and don't stop processing of other assemblies:

- **Missing assemblies**: Skipped gracefully, error recorded
- **Network errors**: Reported with details
- **Conversion errors** (e.g., >36 chains): CIF still written, PDB skipped, error recorded
- **Invalid PDB codes**: No assemblies found, handled gracefully

Check the `errors` list in results to see what went wrong with specific PDBs or assemblies.

## Testing

```bash
python -m pytest tests/ -v
```

All 28 tests pass, covering:
- Assembly discovery and API parsing
- CIF file fetching and caching
- CIF to PDB conversion
- Chain ID remapping with extended IDs
- File I/O and folder structure
- CLI interface
- Error handling

## Development notes

Each PDB ID is stored in lowercase folders and filenames throughout the tool (API queries use lowercase, output folders/files use lowercase, return values use lowercase) for consistency.

Chain ID remapping uses deterministic alphabetical ordering to ensure reproducible, reproducible results across runs and environments.

## References

- [PDBe REST API documentation](https://www.ebi.ac.uk/pdbe/api)
- [mmCIF format specification](https://mmcif.wwpdb.org)
- [PDB file format documentation](https://www.wwpdb.org/documentation/file-format)
- [BioPython MMCIFParser](https://biopython.org)

## License

Part of the histo_tools family of structural biology utilities.
