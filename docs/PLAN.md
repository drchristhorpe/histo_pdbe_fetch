# histo_pdbe_fetch design plan

## 1. Purpose

Fetch metadata about all biological unit assemblies from the PDBe (Protein Data
Bank in Europe) REST API for one or more PDB structure ids, writing each assembly
as a separate JSON file organized in a folder hierarchy. For each PDB, create a
subfolder named by the PDB id, and write individual assembly metadata files as
`{pdb_id}__1.json`, `{pdb_id}__2.json`, etc.

**Scope**: All biological unit assemblies (assembly 1, 2, 3, ...) for each PDB.
Out of scope: crystal packing (`assembly 0`) and non-biological forms. Per-PDB
querying is required — the PDBe API offers no bulk endpoint for assembly metadata.

## 2. Data source: PDBe PISA API

The PDBe exposes assembly metadata via JSON files served from the PDBe-KB
filesystem, derived from [CCP4 PISA](http://www.ebi.ac.uk/msd-srv/pisa/)
(Protein Interfaces, Surfaces and Assemblies).

**Endpoint pattern**: For each PDB id + assembly id:
```
https://www.ebi.ac.uk/pdbe/static/files/pisa/{pdb_id}/{pdb_id}-assembly{assembly_id}.json
```

**Example**: `1AO7`, assembly 1 → `https://www.ebi.ac.uk/pdbe/static/files/pisa/1ao7/1ao7-assembly1.json`

PDB ids are always **lowercase** in URLs; responses return uppercase `pdb_id` fields.

## 3. Fetching strategy & key design decisions

### Assembly discovery: finding all assemblies per PDB
A PDB can have multiple defined assemblies (assembly 1, 2, 3, ...). To discover
how many assemblies exist for a given PDB, **Decision: attempt to fetch assembly
1, 2, 3, ... sequentially until a 404 is received** (simple, no extra API calls,
matches histo_stcrdab_fetch's per-item fetch pattern). The tool halts at the
first missing assembly (if assembly 3 returns 404, don't try assembly 4).

- Rationale: Avoids a second API call per PDB to discover assembly count;
  leverages the fact that assembly ids are contiguous integers starting at 1.
- Edge case: If only assembly 1 exists, this is still one call (correct). If
  assemblies 1, 2, 3 exist, three calls per PDB (acceptable, small overhead).

### Per-PDB vs. bulk querying
Unlike `histo_tcr_info_fetch`'s `summary/all` bulk endpoint, PDBe has **no
advertised JSON bulk endpoint for assemblies**. Each assembly must be fetched
individually per (pdb_id, assembly_id) pair. **Decision: implement per-PDB
fetching with support for multiple PDBs in one CLI invocation** (both single and
batch input supported). Parallel requests are optional in the library; CLI runs
sequentially by default (users call this once per pipeline setup, not
interactively). A legacy XML bulk endpoint exists but is being deprecated —
don't use it unless a v0.2+ requirement for bulk performance emerges.

### Caching
Responses are cached on disk (default `~/.cache/histo_pdbe_fetch/`, override
with `--cache-dir`) keyed by URL hash. `--refresh` bypasses the cache.
No per-request throttling is added — four parallel requests per second is
well within PDBe's terms of service for a tool run that fetches a batch of
PDBs once per pipeline setup (not interactively hammering the API).

## 4. Response parsing & per-PDB fetching

Each PDB's assemblies are fetched and written independently to the output folder.

### Parsing (pure function, network-free, unit-tested)

```python
def parse_assembly_json(json_text: str) -> dict:
    """Parse a PDBe PISA assembly JSON response.
    
    Returns the assembly dict from the response (or None if parsing fails).
    Used only for parsing already-fetched text; no network.
    """
```

Extracts the top-level assembly information from the PISA response:
- `pdb_id` (uppercased)
- `assembly_id`
- Metrics: `dissociation_energy`, `buried_surface_area`, `accessible_surface_area`,
  `solvation_energy_gain`, `entropy`, `symmetry_number`
- Composition data: `formula`, `composition` (chains + ligand labels)
- Interface count and interface details (bond counts, areas)

### Fetching (network + cache, thin wrapper)

```python
def fetch_pdbe_assembly(pdb_id: str, assembly_id: int, cache_dir: Path, refresh: bool) -> dict | None:
    """Fetch a specific assembly for a single PDB id.
    
    Returns parsed assembly dict, or None if the assembly doesn't exist.
    Raises on network errors or unparseable responses.
    """
```

Calls the PDBe API with a lowercase pdb_id, caches on disk, returns parsed result.

### Discovery & writing per PDB

```python
def fetch_and_write_pdb_assemblies(pdb_id: str, output_dir: Path, cache_dir: Path, refresh: bool) -> dict:
    """Fetch all assemblies for one PDB, write each to output folder.
    
    Returns dict with "pdb_id", "assembly_count", "written_paths", "errors".
    """
```

- Lowercase the PDB id for API queries
- Try to fetch assembly 1, 2, 3, ... until a 404 is encountered
- For each successful fetch:
  - Create folder: `output_dir/{PDB_ID_UPPERCASE}/` if not exists
  - Write file: `output_dir/{PDB_ID_UPPERCASE}/{pdb_id_uppercase}__{assembly_id}.json`
  - Preserve exact JSON from PDBe (no field renaming)
- Return summary: how many assemblies were written, any per-assembly errors

## 5. JSON Schema per assembly file (v0.1.0 — initial)

Each written file is a single assembly's metadata, validated against
`src/histo_pdbe_fetch/schema/assembly.schema.json` (JSON Schema draft 2020-12).
No envelope wrapper; each file is the assembly dict directly:

```jsonc
{
  "PISA": {
    "pdb_id": "1AO7",
    "assembly_id": 1,
    "pisa_version": "2.0",
    "assembly": {
      "composition": "A-2A[NA](2)[ADP][RHO]",
      "formula": "A(2)a(2)",
      "size": 6,
      "macromolecular_size": 2,
      "symmetry_number": 1,
      "dissociation_energy": -3.0,
      "accessible_surface_area": 12345.67,
      "buried_surface_area": 1234.56,
      "solvation_energy_gain": -25.43,
      "entropy": 45.2,
      "interface_count": 1,
      "interfaces": [
        {
          "interface_id": "A-B",
          "interface_area": 1234.56,
          "stabilization_energy": -15.2,
          "solvation_energy": -25.1,
          "p_value": 0.05,
          "number_interface_residues": 45,
          "number_hydrogen_bonds": 12,
          "number_salt_bridges": 3,
          "number_disulfide_bonds": 0,
          "number_covalent_bonds": 0,
          "number_other_bonds": 2
        }
      ]
    }
  }
}
```

**Nullability**: Numeric fields can be `null` if the PISA computation didn't
produce a value. String fields (composition, formula) are always present if
the assembly exists.

**Files written** (one per assembly):
```
output_dir/
  1AO7/
    1ao7__1.json
    1ao7__2.json
  1BAK/
    1bak__1.json
```

`schema_version` (within the bundled schema) follows semver; breaking changes
(renamed/removed fields) bump the minor version pre-1.0.

## 6. Library API

```python
from histo_pdbe_fetch import PDBeFetcher

fetcher = PDBeFetcher(cache_dir=None, refresh=False)
# cache_dir=None -> ~/.cache/histo_pdbe_fetch

result = fetcher.run(pdb_ids=["1ao7", "1bak", "2hla"], output_dir="./structures/")
# result: {"pdb_results": [
#   {"pdb_id": "1AO7", "assembly_count": 2, "written_paths": ["./structures/1AO7/1ao7__1.json", ...], "errors": []},
#   ...
# ], "total_assemblies_written": 5, "total_pdbs_processed": 3}
```

The library:
- `run(pdb_ids, output_dir)` — fetch all assemblies for each PDB, write to output folder hierarchy
- Returns a dict with per-PDB results (assembly count, written file paths, errors)
- Creates folder structure automatically (`output_dir/{PDB_ID}/`)

Lower-level functions (`fetch_pdbe_assembly`, `parse_assembly_json`,
`fetch_and_write_pdb_assemblies`) are also public, for callers who want to
fetch individual assemblies or handle I/O separately.

## 7. CLI

```
histo-pdbe-fetch --output DIR [--cache-dir DIR] [--refresh] PDB_ID [PDB_ID ...]
```

- `--output` (required): output directory (will be created if missing). Assemblies
  are written as `output_dir/{PDB_ID}/{pdb_id}__{assembly_id}.json`.
- `--cache-dir` (optional): override the default `~/.cache/histo_pdbe_fetch`.
- `--refresh` (flag): bypass cache and re-fetch every PDB's assemblies.
- `PDB_ID` (positional, one or more): PDB ids to fetch (e.g., `1ao7 1bak 2hla`).
  Ids are case-insensitive; lowercased before API queries, uppercased in folder/file names.

Rich console output on completion: a summary table showing:
- PDB ids processed
- Per-PDB assembly count
- Total assemblies written
- Cache location
- Output directory path

Example:
```
$ histo-pdbe-fetch --output ./pdb_structures 1ao7 1bak
Processing 1AO7... fetched 2 assemblies
Processing 1BAK... fetched 1 assembly
Total: 2 PDBs, 3 assemblies written to ./pdb_structures/
Cache: ~/.cache/histo_pdbe_fetch/
```

## 8. Claude skill

`skills/histo-pdbe-fetch/SKILL.md` documents the CLI and the JSON output
schema, so an agent can request assembly metadata for a set of PDBs ("fetch
assembly data for these PDB ids", "get biological assembly info for 1ao7 and
1bak").

## 9. Package layout

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
    __init__.py
    http.py                # cached_get(): disk cache, refresh, User-Agent
    core.py                # PDBeFetcher class, run(), fetch_and_write_pdb_assemblies()
    cli.py                 # Click CLI entry point
    py.typed
    sources/
      __init__.py
      pdbe.py              # parse_assembly_json(), fetch_pdbe_assembly()
    schema/
      assembly.schema.json
  skills/histo-pdbe-fetch/SKILL.md
  tests/
    fixtures/
      pdbe/                # real PDBe API responses for assembly queries
        1ao7-assembly1.json
        1ao7-assembly2.json
        1bak-assembly1.json
        1a0o-assembly1.json (404 case)
    test_pdbe.py
    test_core.py
    test_cli.py
  tmp/
    .gitkeep
```

## 10. Testing plan

Parsing functions are tested against small, real PDBe API responses (actual
`assembly1.json`, `assembly2.json` files from diverse PDBs, plus 404 cases)
— no network access, no synthetic data. `fetch_pdbe_assembly`/HTTP plumbing
(`http.py`) is exercised by one live end-to-end run (see §11).

`test_core.py` tests `fetch_and_write_pdb_assemblies()`:
- Successful fetch and write (folder + file creation, correct naming)
- Multiple assemblies per PDB
- 404 handling (assembly doesn't exist, continue to next PDB)
- File output to correct directory structure

`test_cli.py` uses `click.testing.CliRunner` with monkeypatched fetch layer,
covering:
- Single valid PDB → files written to `output_dir/{PDB_ID}/`
- Multiple valid PDBs
- One invalid/missing PDB among valid ones (fetch continues)
- `--output-dir` creation and structure
- `--cache-dir`/`--refresh` flag passing
- Case-insensitive PDB id input (lowercased for API, uppercased in folder/file names)

A `jsonschema`-based test validates each written assembly JSON file against
the bundled schema.

## 11. Workflow

1. Write this plan, commit-worthy on its own. ✓
2. Scaffold the package layout.
3. Implement `http.py`, then `sources/pdbe.py` (parse function first,
   fixture-tested, then the thin fetch wrapper), then `core.py`, `cli.py`.
4. Write `CHANGELOG.md` as work proceeds (Keep a Changelog format).
5. Write tests against committed real PDBe API responses (including multiple
   assemblies per PDB, and missing assembly cases).
6. Run the full pipeline live:
   ```bash
   histo-pdbe-fetch --output tmp/pdb_structures 1ao7 1bak 2hla 1a0o
   ```
   Inspect `tmp/pdb_structures/` folder structure and sample JSON files for Chris to eyeball.
7. Pause for approval — commit and write `README.md` + `CLAUDE.md` + `SKILL.md`
   only once approved.
