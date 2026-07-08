# histo-pdbe-fetch skill

Fetch biological unit assembly structures from the PDBe (Protein Data Bank in Europe).

## Commands

### Fetch PDB assemblies
```
histo-pdbe-fetch --output <output_dir> [--cache-dir <cache_dir>] [--refresh] <pdb_id> [<pdb_id> ...]
```

Fetch all biological unit assemblies for one or more PDB codes.

**Parameters:**
- `--output` (required): Output directory where structure files will be written
- `--cache-dir` (optional): Directory for caching downloaded files (default: `~/.cache/histo_pdbe_fetch/`)
- `--refresh` (flag): Bypass cache and re-download all assemblies
- `pdb_id` (positional, one or more): 4-character PDB codes (case-insensitive)

**Output:**
- Hierarchical folder structure: `output_dir/{pdb_id_lowercase}/{pdb_id_lowercase}__{assembly_id}.{cif,pdb}`
- For each assembly: mmCIF format file + PDB format file (converted from CIF)
- Chain ID remapping for extended IDs documented in PDB REMARK lines

**Example:**
```bash
histo-pdbe-fetch --output ./structures 1ao7 1hhk
# Creates:
# structures/1ao7/1ao7__1.cif
# structures/1ao7/1ao7__1.pdb
# structures/1ao7/1ao7__2.cif
# structures/1ao7/1ao7__2.pdb
# structures/1hhk/1hhk__1.cif
# structures/1hhk/1hhk__1.pdb
# structures/1hhk/1hhk__2.cif
# structures/1hhk/1hhk__2.pdb
```

## Library API

```python
from histo_pdbe_fetch import PDBeFetcher

fetcher = PDBeFetcher(cache_dir=None, refresh=False)
result = fetcher.run(pdb_ids=["1ao7", "1hhk"], output_dir="./structures/")
```

**Returns:**
```python
{
  "pdb_results": [
    {
      "pdb_id": "1ao7",
      "assembly_count": 2,
      "written_paths": [
        "./structures/1ao7/1ao7__1.cif",
        "./structures/1ao7/1ao7__1.pdb",
        "./structures/1ao7/1ao7__2.cif",
        "./structures/1ao7/1ao7__2.pdb"
      ],
      "errors": []
    },
    # ... more PDBs
  ],
  "total_assemblies_written": 4,
  "total_pdbs_processed": 2
}
```

## Features

### Automatic Chain ID Remapping
Some biological unit assemblies have extended chain identifiers (e.g., "A-1", "B-2") that exceed PDB format's single-character limit. The tool automatically remaps these to A-Z, then 0-9, documenting the mapping in PDB REMARK lines:

```
REMARK   1 CHAIN ID REMAPPING FOR PDB FORMAT COMPATIBILITY
REMARK   1 CHAIN A-1 REMAPPED TO A
REMARK   1 CHAIN B-2 REMAPPED TO C
```

Original chain IDs can be recovered from the REMARK documentation.

### Efficient Caching
HTTP responses are cached on disk by URL hash, avoiding redundant downloads:
- Default cache: `~/.cache/histo_pdbe_fetch/`
- Use `--refresh` to bypass cache and re-fetch

### Per-Assembly Discovery
The tool queries the PDBe API to discover all available biological unit assemblies for each PDB code, then fetches each assembly independently.

## Data Sources

- **Assembly Discovery**: PDBe API v2 endpoint
  ```
  https://www.ebi.ac.uk/pdbe/api/v2/pdb/entry/assembly/{pdb_id}
  ```

- **Structure Files**: PDBe static download endpoint (gzipped mmCIF)
  ```
  https://www.ebi.ac.uk/pdbe/static/entry/download/{pdb_id}-assembly{assembly_id}.cif.gz
  ```

## File Formats

- **CIF (Crystallographic Information File)**: Raw mmCIF format from PDBe, includes extended chain IDs
- **PDB (Protein Data Bank)**: Generated from CIF via BioPython, chain IDs remapped for format compatibility

## Error Handling

Errors are reported per assembly:
- Missing assemblies: skipped gracefully, error recorded
- Network errors: reported with details
- Conversion errors (e.g., >36 chains): CIF still written, PDB skipped, error recorded

The tool continues processing remaining PDBs and assemblies even if individual ones fail.

## Requirements

- Python 3.11+
- BioPython >= 1.85
- requests >= 2.32
- click >= 8.1
- rich >= 13.0
