"""Tests for PDBe source module (discover and fetch functions)."""

from __future__ import annotations

from pathlib import Path

import pytest

from histo_pdbe_fetch.sources.pdbe import discover_assemblies, fetch_cif_file, cif_to_pdb


class TestDiscoverAssemblies:
    """Test discover_assemblies function."""

    def test_discover_with_mocked_api(self, tmp_path: Path, monkeypatch) -> None:
        """Discover returns assembly IDs from API response."""
        def mock_cached_get(url: str, cache_dir: Path, refresh: bool) -> str:
            # Mock PDBe API response for assembly discovery
            return '{"1ao7": [{"assembly_id": "1"}, {"assembly_id": "2"}]}'

        monkeypatch.setattr(
            "histo_pdbe_fetch.sources.pdbe.cached_get", mock_cached_get
        )

        result = discover_assemblies("1AO7", cache_dir=tmp_path, refresh=False)

        assert result == ["1", "2"]

    def test_discover_single_assembly(self, tmp_path: Path, monkeypatch) -> None:
        """Discover PDB with single assembly."""
        def mock_cached_get(url: str, cache_dir: Path, refresh: bool) -> str:
            return '{"1hhk": [{"assembly_id": "1"}]}'

        monkeypatch.setattr(
            "histo_pdbe_fetch.sources.pdbe.cached_get", mock_cached_get
        )

        result = discover_assemblies("1HHK", cache_dir=tmp_path, refresh=False)

        assert result == ["1"]

    def test_discover_multiple_assemblies_sorted(self, tmp_path: Path, monkeypatch) -> None:
        """Discover returns assembly IDs sorted numerically."""
        def mock_cached_get(url: str, cache_dir: Path, refresh: bool) -> str:
            return '{"1pdb": [{"assembly_id": "3"}, {"assembly_id": "1"}, {"assembly_id": "2"}]}'

        monkeypatch.setattr(
            "histo_pdbe_fetch.sources.pdbe.cached_get", mock_cached_get
        )

        result = discover_assemblies("1PDB", cache_dir=tmp_path, refresh=False)

        assert result == ["1", "2", "3"]

    def test_discover_404_returns_empty(self, tmp_path: Path, monkeypatch) -> None:
        """Discover returns empty list on 404 (PDB not found)."""
        def mock_cached_get(url: str, cache_dir: Path, refresh: bool) -> str:
            raise Exception("404 Not Found")

        monkeypatch.setattr(
            "histo_pdbe_fetch.sources.pdbe.cached_get", mock_cached_get
        )

        result = discover_assemblies("XXXX", cache_dir=tmp_path, refresh=False)
        assert result == []

    def test_discover_pdb_id_lowercase(self, tmp_path: Path, monkeypatch) -> None:
        """Discover uses lowercase PDB ID in API call."""
        called_urls = []

        def mock_cached_get(url: str, cache_dir: Path, refresh: bool) -> str:
            called_urls.append(url)
            return '{"1ao7": [{"assembly_id": "1"}]}'

        monkeypatch.setattr(
            "histo_pdbe_fetch.sources.pdbe.cached_get", mock_cached_get
        )

        discover_assemblies("1AO7", cache_dir=tmp_path, refresh=False)

        assert len(called_urls) == 1
        assert "1ao7" in called_urls[0]  # URL should have lowercase PDB ID


class TestChainIDRemapper:
    """Test chain ID remapping functionality."""

    def test_analyze_chains_no_extended(self) -> None:
        """Analyze chains finds normal single-character chain IDs."""
        from histo_pdbe_fetch.chain_remapper import ChainIDRemapper

        cif_content = """data_1hhk
loop_
_atom_site.group_PDB
_atom_site.auth_asym_id
_atom_site.auth_seq_id
ATOM A 1
ATOM A 2
ATOM B 1
"""
        chains = ChainIDRemapper.analyze_chains(cif_content)
        assert set(chains) == {"A", "B"}

    def test_analyze_chains_with_extended(self) -> None:
        """Analyze chains finds extended chain IDs like A-1, B-2."""
        from histo_pdbe_fetch.chain_remapper import ChainIDRemapper

        cif_content = """data_1ao7
loop_
_atom_site.group_PDB
_atom_site.auth_asym_id
_atom_site.auth_seq_id
ATOM A-1 1
ATOM A-2 1
ATOM B-1 1
"""
        chains = ChainIDRemapper.analyze_chains(cif_content)
        assert "A-1" in chains
        assert "A-2" in chains
        assert "B-1" in chains

    def test_analyze_chains_stops_at_anisotrop_loop(self) -> None:
        """Regression: the _atom_site scan must stop at the end of its loop.

        High-resolution X-ray entries carry an `_atom_site_anisotrop` loop right
        after `_atom_site`. Its data rows also start with a digit, so a scan that
        skips (rather than stops on) `loop_`/`_`-prefixed lines reads them as more
        atom_site rows and mistakes the anisotrop atom-name column for chain IDs —
        inflating the count past the 36-chain PDB ceiling and silently dropping the
        structure. Only the real chains (A) must be returned here, never atom names.
        """
        from histo_pdbe_fetch.chain_remapper import ChainIDRemapper

        cif_content = """data_3o4l
loop_
_atom_site.group_PDB
_atom_site.id
_atom_site.auth_asym_id
_atom_site.auth_atom_id
ATOM 1 A N
ATOM 2 A CA
ATOM 3 A O
#
loop_
_atom_site_anisotrop.id
_atom_site_anisotrop.auth_atom_id
1 N
2 CA
3 O
"""
        chains = ChainIDRemapper.analyze_chains(cif_content)
        assert set(chains) == {"A"}
        for atom_name in ("N", "CA", "O"):
            assert atom_name not in chains

    def test_create_mapping_deterministic(self) -> None:
        """Mapping is deterministic and alphabetically ordered."""
        from histo_pdbe_fetch.chain_remapper import ChainIDRemapper

        chains = ["A-1", "A-2", "B-1", "C"]
        mapping = ChainIDRemapper.create_mapping(chains)

        assert mapping["A-1"] == "A"
        assert mapping["A-2"] == "B"
        assert mapping["B-1"] == "C"
        assert mapping["C"] == "D"

    def test_create_mapping_too_many_chains(self) -> None:
        """Mapping raises ValueError if more than 36 chains."""
        from histo_pdbe_fetch.chain_remapper import ChainIDRemapper

        chains = [f"C{i}" for i in range(37)]  # 37 chains
        with pytest.raises(ValueError, match="Too many chains"):
            ChainIDRemapper.create_mapping(chains)
