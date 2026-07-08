# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.1.0] - 2026-07-08

### Added

- Initial release: `PDBeFetcher` class for fetching biological unit assembly structures from PDBe
- Per-PDB assembly discovery: queries PDBe API to find all available assemblies for each PDB code
- Two-file output per assembly:
  - `{pdb_id}__{assembly_id}.cif` — mmCIF format coordinate file (from PDBe, gzipped download)
  - `{pdb_id}__{assembly_id}.pdb` — PDB format coordinate file (converted from CIF via BioPython)
- Hierarchical folder structure: `output_dir/{pdb_id_lowercase}/{pdb_id_lowercase}__{assembly_id}.{cif|pdb}`
- **Chain ID remapping**: Automatically handles extended chain IDs (e.g., "A-1", "B-2") that exceed PDB format's single-character limit
  - Maps chains deterministically to A-Z, then 0-9 (up to 36 chains)
  - Documents original → remapped chain IDs in PDB REMARK lines
  - Supports structures with normal chain IDs without modification
- Disk caching: all HTTP responses cached under `~/.cache/histo_pdbe_fetch/` with `--refresh` flag to bypass cache
- CLI: `histo-pdbe-fetch --output DIR [--cache-dir DIR] [--refresh] PDB_ID [PDB_ID ...]`
- Library API: `PDBeFetcher.run(pdb_ids, output_dir)` returns per-PDB results with all written file paths and errors
- PDB id casing: all PDB ids normalized to lowercase throughout (folders, files, return values)
