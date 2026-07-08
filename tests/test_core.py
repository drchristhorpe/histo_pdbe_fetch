"""Tests for core module (PDBeFetcher and file writing)."""

from __future__ import annotations

from pathlib import Path

import pytest

from histo_pdbe_fetch.core import PDBeFetcher, fetch_and_write_pdb_assemblies


class TestFetchAndWritePdbAssemblies:
    """Test fetch_and_write_pdb_assemblies (folder/file writing)."""

    def test_write_single_assembly(self, tmp_path: Path, monkeypatch) -> None:
        """Fetch and write a single assembly with CIF and PDB files."""
        def mock_discover(pdb_id: str, cache_dir: Path, refresh: bool) -> list[str]:
            return ["1"]

        def mock_fetch_cif(pdb_id: str, assembly_id: str, cache_dir: Path, refresh: bool) -> str | None:
            return "data_1ao7\nloop_\n_atom_site.auth_asym_id\nA"

        def mock_cif_to_pdb(cif_content: str, pdb_id: str) -> str:
            return "ATOM      1  N   ALA A   1       1.0   2.0   3.0  1.00  0.00           N"

        monkeypatch.setattr("histo_pdbe_fetch.core.discover_assemblies", mock_discover)
        monkeypatch.setattr("histo_pdbe_fetch.core.fetch_cif_file", mock_fetch_cif)
        monkeypatch.setattr("histo_pdbe_fetch.core.cif_to_pdb", mock_cif_to_pdb)

        result = fetch_and_write_pdb_assemblies("1ao7", tmp_path, tmp_path, False)

        assert result["pdb_id"] == "1ao7"
        assert result["assembly_count"] == 1
        # Should have both CIF and PDB files
        assert len(result["written_paths"]) == 2
        assert any("1ao7__1.cif" in p for p in result["written_paths"])
        assert any("1ao7__1.pdb" in p for p in result["written_paths"])
        assert (tmp_path / "1ao7" / "1ao7__1.cif").exists()
        assert (tmp_path / "1ao7" / "1ao7__1.pdb").exists()

    def test_write_multiple_assemblies(self, tmp_path: Path, monkeypatch) -> None:
        """Fetch and write multiple assemblies for one PDB."""
        def mock_discover(pdb_id: str, cache_dir: Path, refresh: bool) -> list[str]:
            return ["1", "2"]

        def mock_fetch_cif(pdb_id: str, assembly_id: str, cache_dir: Path, refresh: bool) -> str | None:
            return f"data_1ao7\nloop_\n_atom_site.auth_asym_id\nA"

        def mock_cif_to_pdb(cif_content: str, pdb_id: str) -> str:
            return "ATOM      1  N   ALA A   1       1.0   2.0   3.0  1.00  0.00           N"

        monkeypatch.setattr("histo_pdbe_fetch.core.discover_assemblies", mock_discover)
        monkeypatch.setattr("histo_pdbe_fetch.core.fetch_cif_file", mock_fetch_cif)
        monkeypatch.setattr("histo_pdbe_fetch.core.cif_to_pdb", mock_cif_to_pdb)

        result = fetch_and_write_pdb_assemblies("1ao7", tmp_path, tmp_path, False)

        assert result["pdb_id"] == "1ao7"
        assert result["assembly_count"] == 2
        # 2 assemblies × 2 files each (CIF + PDB) = 4 files
        assert len(result["written_paths"]) == 4
        assert (tmp_path / "1ao7" / "1ao7__1.cif").exists()
        assert (tmp_path / "1ao7" / "1ao7__1.pdb").exists()
        assert (tmp_path / "1ao7" / "1ao7__2.cif").exists()
        assert (tmp_path / "1ao7" / "1ao7__2.pdb").exists()

    def test_folder_naming_lowercase(self, tmp_path: Path, monkeypatch) -> None:
        """Folder name uses lowercase PDB id."""
        def mock_discover(pdb_id: str, cache_dir: Path, refresh: bool) -> list[str]:
            return ["1"]

        def mock_fetch_cif(pdb_id: str, assembly_id: str, cache_dir: Path, refresh: bool) -> str | None:
            return "data_1hhk\nloop_\n_atom_site.auth_asym_id\nA"

        def mock_cif_to_pdb(cif_content: str, pdb_id: str) -> str:
            return "ATOM      1"

        monkeypatch.setattr("histo_pdbe_fetch.core.discover_assemblies", mock_discover)
        monkeypatch.setattr("histo_pdbe_fetch.core.fetch_cif_file", mock_fetch_cif)
        monkeypatch.setattr("histo_pdbe_fetch.core.cif_to_pdb", mock_cif_to_pdb)

        result = fetch_and_write_pdb_assemblies("1HHK", tmp_path, tmp_path, False)

        # PDB id should be lowercase
        assert result["pdb_id"] == "1hhk"
        # Folder should be lowercase
        assert (tmp_path / "1hhk").exists()

    def test_file_naming_lowercase_with_assembly_id(self, tmp_path: Path, monkeypatch) -> None:
        """File names use lowercase PDB id and assembly id."""
        def mock_discover(pdb_id: str, cache_dir: Path, refresh: bool) -> list[str]:
            return ["1", "2"]

        def mock_fetch_cif(pdb_id: str, assembly_id: str, cache_dir: Path, refresh: bool) -> str | None:
            return "data_1hhk"

        def mock_cif_to_pdb(cif_content: str, pdb_id: str) -> str:
            return "ATOM      1"

        monkeypatch.setattr("histo_pdbe_fetch.core.discover_assemblies", mock_discover)
        monkeypatch.setattr("histo_pdbe_fetch.core.fetch_cif_file", mock_fetch_cif)
        monkeypatch.setattr("histo_pdbe_fetch.core.cif_to_pdb", mock_cif_to_pdb)

        result = fetch_and_write_pdb_assemblies("1HHK", tmp_path, tmp_path, False)

        # Files should use lowercase PDB id
        assert (tmp_path / "1hhk" / "1hhk__1.cif").exists()
        assert (tmp_path / "1hhk" / "1hhk__1.pdb").exists()
        assert (tmp_path / "1hhk" / "1hhk__2.cif").exists()
        assert (tmp_path / "1hhk" / "1hhk__2.pdb").exists()

    def test_no_assemblies_returns_empty(self, tmp_path: Path, monkeypatch) -> None:
        """PDB with no assemblies returns empty result."""
        def mock_discover(pdb_id: str, cache_dir: Path, refresh: bool) -> list[str]:
            return []  # No assemblies found

        monkeypatch.setattr("histo_pdbe_fetch.core.discover_assemblies", mock_discover)

        result = fetch_and_write_pdb_assemblies("XXXX", tmp_path, tmp_path, False)

        assert result["pdb_id"] == "xxxx"
        assert result["assembly_count"] == 0
        assert result["written_paths"] == []
        assert len(result["errors"]) > 0

    def test_cif_conversion_error_recorded(self, tmp_path: Path, monkeypatch) -> None:
        """Conversion errors are recorded in result."""
        def mock_discover(pdb_id: str, cache_dir: Path, refresh: bool) -> list[str]:
            return ["1"]

        def mock_fetch_cif(pdb_id: str, assembly_id: str, cache_dir: Path, refresh: bool) -> str | None:
            return "data_test"

        def mock_cif_to_pdb(cif_content: str, pdb_id: str) -> str:
            raise ValueError("Too many chains (> 36)")

        monkeypatch.setattr("histo_pdbe_fetch.core.discover_assemblies", mock_discover)
        monkeypatch.setattr("histo_pdbe_fetch.core.fetch_cif_file", mock_fetch_cif)
        monkeypatch.setattr("histo_pdbe_fetch.core.cif_to_pdb", mock_cif_to_pdb)

        result = fetch_and_write_pdb_assemblies("1test", tmp_path, tmp_path, False)

        # CIF should still be written even if PDB conversion fails
        assert (tmp_path / "1test" / "1test__1.cif").exists()
        # PDB should not be written
        assert not (tmp_path / "1test" / "1test__1.pdb").exists()
        # Error should be recorded
        assert any("conversion" in str(e).lower() for e in result["errors"])


class TestPDBeFetcher:
    """Test PDBeFetcher class."""

    def test_run_single_pdb(self, tmp_path: Path, monkeypatch) -> None:
        """Fetcher.run handles a single PDB id."""
        def mock_discover(pdb_id: str, cache_dir: Path, refresh: bool) -> list[str]:
            return ["1"] if pdb_id.lower() == "1hhk" else []

        def mock_fetch_cif(pdb_id: str, assembly_id: str, cache_dir: Path, refresh: bool) -> str | None:
            return "data_1hhk"

        def mock_cif_to_pdb(cif_content: str, pdb_id: str) -> str:
            return "ATOM      1"

        monkeypatch.setattr("histo_pdbe_fetch.core.discover_assemblies", mock_discover)
        monkeypatch.setattr("histo_pdbe_fetch.core.fetch_cif_file", mock_fetch_cif)
        monkeypatch.setattr("histo_pdbe_fetch.core.cif_to_pdb", mock_cif_to_pdb)

        fetcher = PDBeFetcher()
        result = fetcher.run(["1HHK"], tmp_path)

        assert result["total_pdbs_processed"] == 1
        assert result["total_assemblies_written"] == 1
        assert len(result["pdb_results"]) == 1
        assert result["pdb_results"][0]["pdb_id"] == "1hhk"

    def test_run_multiple_pdbs(self, tmp_path: Path, monkeypatch) -> None:
        """Fetcher.run handles multiple PDB ids."""
        def mock_discover(pdb_id: str, cache_dir: Path, refresh: bool) -> list[str]:
            if pdb_id.lower() == "1hhk":
                return ["1", "2"]
            elif pdb_id.lower() == "1ao7":
                return ["1"]
            return []

        def mock_fetch_cif(pdb_id: str, assembly_id: str, cache_dir: Path, refresh: bool) -> str | None:
            return "data_test"

        def mock_cif_to_pdb(cif_content: str, pdb_id: str) -> str:
            return "ATOM      1"

        monkeypatch.setattr("histo_pdbe_fetch.core.discover_assemblies", mock_discover)
        monkeypatch.setattr("histo_pdbe_fetch.core.fetch_cif_file", mock_fetch_cif)
        monkeypatch.setattr("histo_pdbe_fetch.core.cif_to_pdb", mock_cif_to_pdb)

        fetcher = PDBeFetcher()
        result = fetcher.run(["1HHK", "1AO7"], tmp_path)

        assert result["total_pdbs_processed"] == 2
        assert result["total_assemblies_written"] == 3  # 2 + 1
        assert len(result["pdb_results"]) == 2

    def test_output_dir_created(self, tmp_path: Path, monkeypatch) -> None:
        """Fetcher creates output directory if missing."""
        output_dir = tmp_path / "nonexistent" / "deep" / "path"
        assert not output_dir.exists()

        def mock_discover(pdb_id: str, cache_dir: Path, refresh: bool) -> list[str]:
            return []

        monkeypatch.setattr("histo_pdbe_fetch.core.discover_assemblies", mock_discover)

        fetcher = PDBeFetcher()
        fetcher.run(["1XXX"], output_dir)

        assert output_dir.exists()

    def test_cache_dir_default(self, tmp_path: Path) -> None:
        """PDBeFetcher uses default cache dir when not specified."""
        fetcher = PDBeFetcher(cache_dir=None)
        # Default cache should be under ~/.cache/
        assert "cache" in str(fetcher.cache_dir).lower()

    def test_cache_dir_custom(self, tmp_path: Path) -> None:
        """PDBeFetcher respects custom cache directory."""
        fetcher = PDBeFetcher(cache_dir=tmp_path)
        assert fetcher.cache_dir == tmp_path
