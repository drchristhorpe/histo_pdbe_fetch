# histo_pdbe_fetch design plan

## 1. Purpose

Fetch all biological unit assembly structures from the PDBe (Protein Data
Bank in Europe) API for one or more PDB structure ids, writing each assembly
as coordinate files (CIF and PDB format) organized in a folder hierarchy. For
each PDB, create a subfolder named by the PDB id (lowercase), and write individual
assembly files as `{pdb_id}__1.cif`, `{pdb_id}__1.pdb`, `{pdb_id}__2.cif`,
`{pdb_id}__2.pdb`, etc.

**Scope**: All biological unit assemblies (assembly 1, 2, 3, ...) for each PDB.
Out of scope: crystal packing (`assembly 0`) and non-biological forms. Per-PDB
assembly discovery is required — the PDBe API's assembly discovery endpoint returns
a list of available assembly ids for each PDB.

## 2. Data source: PDBe API

The PDBe exposes assembly discovery and structure files via two API endpoints:

### Assembly discovery endpoint
Queries all available biological unit assemblies for a given PDB:
```
https://www.ebi.ac.uk/pdbe/api/v2/pdb/entry/assembly/{pdb_id}
```

Returns JSON list of assembly objects with `assembly_id` fields (e.g., "1", "2", "3").
Example: `1AO7` → returns assemblies 1 and 2 in JSON array.

### Structure file endpoint
Downloads biological unit assemblies in gzipped mmCIF format:
```
https://www.ebi.ac.uk/pdbe/static/entry/download/{pdb_id}-assembly{assembly_id}.cif.gz
```

Example: `1AO7`, assembly 1 → `https://www.ebi.ac.uk/pdbe/static/entry/download/1ao7-assembly1.cif.gz`

PDB ids are always **lowercase** in URLs.

## 3. Fetching strategy & key design decisions

### Assembly discovery: finding all assemblies per PDB
A PDB can have multiple defined assemblies (assembly 1, 2, 3, ...). The PDBe API
provides a single discovery endpoint that returns a JSON list of all available
assemblies. **Decision: Call the discovery endpoint once per PDB** (efficient,
one API call, no sequential trial-and-error).

- Rationale: Single API call returns complete assembly list; no guessing required.
- Failure mode: PDB not found → empty list returned, graceful handling.

### Structure file fetching
For each discovered assembly, **Decision: download gzipped mmCIF files from PDBe**
(official source, complete and consistent).

- PDB format files are generated locally from CIF via BioPython PDBIO
- Rationale: PDB format files are available from PDBe only for the first assembly
  of most entries; CIF files are available for all assemblies.

### Chain ID remapping for extended chain identifiers
Some biological unit assemblies have more than 26 chains, requiring chain IDs like
"A-1", "A-2", "B-1", etc. These exceed PDB format's single-character limit.

**Decision: Automatic chain ID remapping during CIF→PDB conversion**
- Remap extended chain IDs to A-Z, then 0-9 (up to 36 chains max)
- Deterministic alphabetical mapping: sorted chain IDs → sequential A-Z, 0-9
- Document original → remapped chain IDs in PDB REMARK lines
- Structures with normal chain IDs (A, B, C, ...) are unaffected
- Raise ValueError if >36 unique chains (prevents silent data loss)

Rationale: Allows PDB format output for all biological units; users can recover
original chain IDs from REMARK documentation; deterministic mapping ensures
reproducibility.

### Per-PDB vs. bulk querying
PDBe offers a per-assembly discovery endpoint (one call per PDB returns all
assembly ids). **Decision: implement per-PDB discovery with support for multiple
PDBs in one CLI invocation**. Parallel requests are optional in the library; CLI
runs sequentially by default (users call this once per pipeline setup, not
interactively).

### Caching
HTTP responses are cached on disk (default `~/.cache/histo_pdbe_fetch/`, override
with `--cache-dir`) keyed by URL hash. `--refresh` bypasses the cache.
No per-request throttling is added — PDBe's terms of service allow typical usage.

## 4. Assembly discovery, structure fetching, & CIF→PDB conversion

Each PDB's assemblies are discovered, fetched, and written independently to the output folder.

### Assembly discovery (network + cache)

```python
def discover_assemblies(pdb_id: str, cache_dir: Path, refresh: bool) -> list[str]:
    """Query PDBe to discover all biological unit assemblies for a PDB.
    
    Returns list of assembly IDs as strings (e.g., ["1", "2", "3"]), sorted numerically.
    Returns empty list if PDB not found.
    """
```

Calls the PDBe assembly discovery API, caches on disk, returns sorted list of assembly ids.

### Structure file fetching (network + cache + decompression)

```python
def fetch_cif_file(pdb_id: str, assembly_id: str, cache_dir: Path, refresh: bool) -> str | None:
    """Download and decompress a biological unit assembly CIF file from PDBe.
    
    Returns decompressed CIF content as string, or None if not found.
    Handles gzip decompression and caches raw gzipped bytes.
    """
```

Downloads gzipped mmCIF file, decompresses it, returns string content.

### CIF to PDB conversion (pure function + chain remapping)

```python
def cif_to_pdb(cif_content: str, pdb_id: str) -> str:
    """Convert CIF format structure to PDB format using BioPython.
    
    Automatically remaps extended chain IDs (e.g., "A-1", "B-2") to
    single characters (A-Z, then 0-9) for PDB format compatibility.
    Documents remapping in PDB REMARK lines.
    
    Raises ValueError if more than 36 unique chains.
    """
```

BioPython's MMCIFParser parses CIF content, ChainIDRemapper handles extended chain ids,
PDBIO writes PDB format. Chain remapping is automatic and transparent.

### Discovery & writing per PDB

```python
def fetch_and_write_pdb_assemblies(pdb_id: str, output_dir: Path, cache_dir: Path, refresh: bool) -> dict:
    """Fetch all assemblies for one PDB, write CIF and PDB files to output folder.
    
    Returns dict with "pdb_id", "assembly_count", "written_paths", "errors".
    """
```

- Lowercase the PDB id for API queries
- Discover all assemblies via assembly discovery endpoint
- For each discovered assembly:
  - Download CIF file via structure download endpoint
  - Convert to PDB format via BioPython (with automatic chain remapping)
  - Create folder: `output_dir/{pdb_id_lowercase}/` if not exists
  - Write files:
    - `output_dir/{pdb_id_lowercase}/{pdb_id_lowercase}__{assembly_id}.cif`
    - `output_dir/{pdb_id_lowercase}/{pdb_id_lowercase}__{assembly_id}.pdb`
- Return summary: how many assemblies were written, any per-assembly errors

## 5. Output file formats and layout

### CIF files
Raw mmCIF format from PDBe (gzip automatically decompressed). Contains full
structural information including extended chain IDs.

### PDB files
PDB format (v3) generated from CIF via BioPython. Chain IDs remapped to single
characters (A-Z, 0-9) if needed, with remapping documented in REMARK lines:

```
REMARK   1 CHAIN ID REMAPPING FOR PDB FORMAT COMPATIBILITY
REMARK   1 CHAIN A-1 REMAPPED TO A
REMARK   1 CHAIN A-2 REMAPPED TO B
ATOM      1  N   MET A   1 ...
```

### Output folder structure
```
output_dir/
  1ao7/
    1ao7__1.cif
    1ao7__1.pdb
    1ao7__2.cif
    1ao7__2.pdb
  1hhk/
    1hhk__1.cif
    1hhk__1.pdb
    1hhk__2.cif
    1hhk__2.pdb
```

PDB ids are **lowercase** in folder names and filenames throughout.

## 6. Library API

```python
from histo_pdbe_fetch import PDBeFetcher, discover_assemblies, fetch_cif_file, cif_to_pdb

# High-level API: fetch multiple PDBs, write all assemblies to disk
fetcher = PDBeFetcher(cache_dir=None, refresh=False)
# cache_dir=None -> ~/.cache/histo_pdbe_fetch

result = fetcher.run(pdb_ids=["1ao7", "1hhk"], output_dir="./structures/")
# result: {
#   "pdb_results": [
#     {"pdb_id": "1ao7", "assembly_count": 2, 
#      "written_paths": ["./structures/1ao7/1ao7__1.cif", "./structures/1ao7/1ao7__1.pdb", ...],
#      "errors": []},
#     {"pdb_id": "1hhk", "assembly_count": 2,
#      "written_paths": ["./structures/1hhk/1hhk__1.cif", "./structures/1hhk/1hhk__1.pdb", ...],
#      "errors": []}
#   ],
#   "total_assemblies_written": 4,
#   "total_pdbs_processed": 2
# }
```

The library:
- `run(pdb_ids, output_dir)` — fetch all assemblies for each PDB, write CIF and PDB files to output folder hierarchy
- Returns a dict with per-PDB results (assembly count, written file paths, errors)
- Creates folder structure automatically (`output_dir/{pdb_id_lowercase}/`)

Lower-level functions for building custom workflows:
- `discover_assemblies(pdb_id, cache_dir, refresh)` — returns list of assembly ids
- `fetch_cif_file(pdb_id, assembly_id, cache_dir, refresh)` — returns decompressed CIF content
- `cif_to_pdb(cif_content, pdb_id)` — converts CIF to PDB with automatic chain remapping
- `cif_to_pdb_with_remapping(cif_content, pdb_id, allow_remapping)` — returns both PDB content and chain mapping dict

## 7. CLI

```
histo-pdbe-fetch --output DIR [--cache-dir DIR] [--refresh] PDB_ID [PDB_ID ...]
```

- `--output` (required): output directory (will be created if missing). Assemblies
  are written as `output_dir/{pdb_id_lowercase}/{pdb_id_lowercase}__{assembly_id}.{cif|pdb}`.
- `--cache-dir` (optional): override the default `~/.cache/histo_pdbe_fetch`.
- `--refresh` (flag): bypass cache and re-fetch every PDB's assemblies.
- `PDB_ID` (positional, one or more): PDB ids to fetch (e.g., `1ao7 1hhk 2hla`).
  Ids are case-insensitive; lowercased throughout (folders, files, API queries).

Rich console output on completion: a summary table showing:
- PDB ids processed
- Per-PDB assembly count and file paths
- Total assemblies written (in CIF and PDB formats)
- Cache location
- Output directory path

Example:
```
$ histo-pdbe-fetch --output ./pdb_structures 1ao7 1hhk
Processing 1ao7... discovered 2 assemblies
  1ao7__1: CIF (646 KB), PDB (463 KB)
  1ao7__2: CIF (1.3 MB), PDB (926 KB)
Processing 1hhk... discovered 2 assemblies
  1hhk__1: CIF (542 KB), PDB (385 KB)
  1hhk__2: CIF (583 KB), PDB (421 KB)
Total: 2 PDBs, 4 assemblies (8 files) written to ./pdb_structures/
Cache: ~/.cache/histo_pdbe_fetch/
```

## 8. Package layout

```
histo_pdbe_fetch/
  .gitignore
  .python-version
  pyproject.toml
  README.md
  CLAUDE.md
  CHANGELOG.md
  docs/
    PLAN.md
  src/histo_pdbe_fetch/
    __init__.py                      # exports PDBeFetcher, discover_assemblies, fetch_cif_file, cif_to_pdb, cif_to_pdb_with_remapping
    http.py                          # cached_get(): disk cache, refresh, User-Agent
    core.py                          # PDBeFetcher class, run(), fetch_and_write_pdb_assemblies()
    cli.py                           # Click CLI entry point
    chain_remapper.py                # ChainIDRemapper class, cif_to_pdb_with_remapping()
    py.typed
    sources/
      __init__.py
      pdbe.py                        # discover_assemblies(), fetch_cif_file(), cif_to_pdb()
  tests/
    test_pdbe.py
    test_core.py
    test_cli.py
  tmp/
    .gitkeep
```

## 9. Testing plan

- `test_pdbe.py`: Unit tests for `discover_assemblies()`, `fetch_cif_file()`, `cif_to_pdb()`,
  and `ChainIDRemapper` with mocked HTTP responses and real CIF fixtures.
  
- `test_core.py`: Integration tests for `fetch_and_write_pdb_assemblies()` and `PDBeFetcher.run()`:
  - Successful fetch, convert, and write (folder + file creation, correct naming)
  - Multiple assemblies per PDB
  - Chain ID remapping verification (REMARK lines present for remapped assemblies)
  - Error handling (missing assemblies, network failures)

- `test_cli.py`: CLI tests using `click.testing.CliRunner` with mocked fetch layer:
  - Single valid PDB → files written to `output_dir/{pdb_id}/`
  - Multiple valid PDBs
  - `--output-dir` creation and structure
  - `--cache-dir`/`--refresh` flag passing
  - Case-insensitive PDB id input (lowercased throughout)

## 10. Decisions & rationale

1. **PDBe API for structure download**: PDBe provides gzipped mmCIF files for all
   assemblies, while PDB format files are only available for the first assembly
   of most entries. CIF → PDB conversion via BioPython is reliable and allows
   consistent output for all assemblies.

2. **Automatic chain ID remapping**: Some biological units require extended chain
   IDs (A-1, A-2, etc.) exceeding PDB's single-character limit. Automatic remapping
   to A-Z, 0-9 allows PDB format output while documenting the mapping in REMARK
   lines, enabling users to recover original chain IDs if needed.

3. **Deterministic chain mapping**: Alphabetically sorted chain IDs ensure
   reproducible, deterministic mapping across runs and users, important for
   reproducible science and comparing results.

4. **Disk caching**: Cache HTTP responses by URL hash to avoid redundant downloads
   during development/re-runs. `--refresh` flag allows bypassing cache when needed.
