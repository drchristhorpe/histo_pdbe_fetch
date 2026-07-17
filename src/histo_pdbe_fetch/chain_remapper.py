"""Chain ID remapping for CIF to PDB conversion.

Handles cases where CIF files have extended chain IDs (e.g., "A-1", "A-2") that
exceed PDB format's single-character limit. Maps to A-Z, then 0-9.
"""

from __future__ import annotations

import re
from io import StringIO

from Bio.PDB import MMCIFParser, PDBIO


class ChainIDRemapper:
    """Remaps extended chain IDs to PDB-compatible single characters."""

    # PDB-compatible chain IDs: A-Z (26) + 0-9 (10) = 36 max
    VALID_CHAIN_IDS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

    @staticmethod
    def analyze_chains(cif_content: str) -> list[str]:
        """Extract all unique chain IDs from CIF content.

        Parses the _atom_site loop_ section to find all unique auth_asym_id values.
        """
        lines = cif_content.split("\n")
        chain_ids = set()

        # Find the loop_ section containing _atom_site
        loop_start = -1
        for i, line in enumerate(lines):
            if line.strip().startswith("loop_"):
                # Check if this loop contains _atom_site
                if i + 1 < len(lines) and "_atom_site" in lines[i + 1]:
                    loop_start = i
                    break

        if loop_start == -1:
            return []

        # Find the column index for auth_asym_id
        auth_asym_id_col = -1
        col_index = 0
        i = loop_start + 1

        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("_atom_site."):
                if "auth_asym_id" in line:
                    auth_asym_id_col = col_index
                col_index += 1
                i += 1
            elif line.startswith("_atom_site"):
                if "auth_asym_id" in line:
                    auth_asym_id_col = col_index
                col_index += 1
                i += 1
            else:
                # End of column headers, data starts here
                break

        if auth_asym_id_col == -1:
            return []

        # Parse data rows and extract chain IDs
        while i < len(lines):
            line = lines[i].strip()
            # End of the _atom_site loop: the next `loop_`, category header
            # (`_...`), block terminator (`#`) or blank line closes it. We must
            # STOP here, not skip past — otherwise a following loop whose data
            # rows also start with a digit (notably `_atom_site_anisotrop`,
            # present in high-resolution X-ray entries) gets read as if it were
            # more atom_site rows, and its atom-name column is mistaken for
            # chain IDs (inflating the count and tripping the 36-chain PDB
            # ceiling). mmCIF guarantees no `_`/`loop_` lines inside a loop's
            # data block, so the first such line is an unambiguous terminator.
            if not line or line.startswith("#") or line.startswith("loop_") or line.startswith("_"):
                break

            # Split by whitespace, handling quoted values
            values = []
            in_quotes = False
            current_val = ""

            for char in line + " ":
                if char == "'" and (not current_val or current_val[-1] != "\\"):
                    in_quotes = not in_quotes
                elif char in (" ", "\t") and not in_quotes:
                    if current_val:
                        values.append(current_val.strip("'\""))
                        current_val = ""
                else:
                    current_val += char

            if current_val:
                values.append(current_val.strip("'\""))

            # Extract the chain ID from the correct column
            if auth_asym_id_col < len(values):
                chain_id = values[auth_asym_id_col].strip()
                if chain_id and chain_id != "?":
                    chain_ids.add(chain_id)

            i += 1

        return sorted(chain_ids)

    @staticmethod
    def create_mapping(chain_ids: list[str]) -> dict[str, str]:
        """Create deterministic mapping from CIF chain IDs to PDB chain IDs.

        Uses alphabetical sort for determinism: A-1→A, A-2→B, B-1→C, etc.
        """
        if len(chain_ids) > len(ChainIDRemapper.VALID_CHAIN_IDS):
            raise ValueError(f"Too many chains ({len(chain_ids)}). PDB format supports max {len(ChainIDRemapper.VALID_CHAIN_IDS)}")

        mapping = {}
        for i, cif_chain_id in enumerate(chain_ids):
            mapping[cif_chain_id] = ChainIDRemapper.VALID_CHAIN_IDS[i]
        return mapping

    @staticmethod
    def remap_pdb_content(pdb_content: str, mapping: dict[str, str]) -> str:
        """Remap chain IDs in PDB content and add REMARK documentation."""
        if not mapping:
            return pdb_content

        lines = pdb_content.split("\n")
        remapped_lines = []
        remark_added = False

        for i, line in enumerate(lines):
            # Add remarks before the first ATOM/HETATM record if not yet added
            if not remark_added and line.startswith(("ATOM", "HETATM")):
                remapped_lines.append("REMARK   1 CHAIN ID REMAPPING FOR PDB FORMAT COMPATIBILITY")
                for orig, new in sorted(mapping.items()):
                    remapped_lines.append(f"REMARK   1 CHAIN {orig} REMAPPED TO {new}")
                remark_added = True

            remapped_lines.append(line)

        return "\n".join(remapped_lines)


def cif_to_pdb_with_remapping(cif_content: str, pdb_id: str, allow_remapping: bool = True) -> tuple[str, dict]:
    """Convert CIF to PDB with automatic chain ID remapping.

    Args:
        cif_content: CIF file content as string
        pdb_id: PDB ID for the structure
        allow_remapping: If True, remap extended chain IDs; if False, let BioPython fail

    Returns:
        Tuple of (PDB content, chain_mapping dict)
        chain_mapping: dict like {'A-1': 'A', 'A-2': 'B'} if remapping occurred

    Raises:
        ValueError: If too many chains for PDB format
        Bio.PDB exceptions: On parsing errors
    """
    # Analyze chains in CIF
    chain_ids = ChainIDRemapper.analyze_chains(cif_content)

    # Check if remapping needed
    needs_remapping = any(len(cid) > 1 for cid in chain_ids)

    if needs_remapping and allow_remapping:
        mapping = ChainIDRemapper.create_mapping(chain_ids)
    else:
        mapping = {}

    # Parse CIF using BioPython
    parser = MMCIFParser(QUIET=True)
    structure = parser.get_structure(pdb_id, StringIO(cif_content))

    # Optionally remap chains in structure
    if mapping:
        for model in structure:
            chains_to_rename = []
            for chain in model:
                orig_id = chain.id
                if orig_id in mapping:
                    chains_to_rename.append((chain, orig_id, mapping[orig_id]))

            # Rename chains (must do separately to avoid conflicts)
            for chain, orig_id, new_id in chains_to_rename:
                chain.id = new_id

    # Convert to PDB format
    output = StringIO()
    io = PDBIO()
    io.set_structure(structure)
    io.save(output)

    pdb_content = output.getvalue()

    # Add remapping documentation to PDB
    if mapping:
        pdb_content = ChainIDRemapper.remap_pdb_content(pdb_content, mapping)

    return pdb_content, mapping
