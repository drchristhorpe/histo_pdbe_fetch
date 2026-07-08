"""Tests for CLI module."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from histo_pdbe_fetch.cli import main


class TestCLI:
    """Test CLI command."""

    def test_cli_required_output(self) -> None:
        """CLI requires --output option."""
        runner = CliRunner()
        result = runner.invoke(main, ["1ao7"])

        assert result.exit_code != 0
        assert "output" in result.output.lower() or "Error" in result.output

    def test_cli_requires_pdb_ids(self, tmp_path: Path) -> None:
        """CLI requires at least one PDB id."""
        runner = CliRunner()
        result = runner.invoke(main, ["--output", str(tmp_path)])

        assert result.exit_code != 0

    def test_cli_single_pdb(self, tmp_path: Path, monkeypatch) -> None:
        """CLI processes single PDB successfully."""
        def mock_write_func(pdb_id: str, output_dir: Path, cache_dir: Path, refresh: bool):
            return {
                "pdb_id": "1ao7",
                "assembly_count": 1,
                "written_paths": [str(output_dir / "1ao7" / "1ao7__1.json")],
                "errors": [],
            }

        monkeypatch.setattr(
            "histo_pdbe_fetch.core.fetch_and_write_pdb_assemblies", mock_write_func
        )

        runner = CliRunner()
        result = runner.invoke(main, ["--output", str(tmp_path), "1ao7"])

        assert result.exit_code == 0
        assert "1ao7" in result.output
        assert "1 assemblies written" in result.output

    def test_cli_multiple_pdbs(self, tmp_path: Path, monkeypatch) -> None:
        """CLI processes multiple PDBs."""
        def mock_write_func(pdb_id: str, output_dir: Path, cache_dir: Path, refresh: bool):
            count = 2 if pdb_id.lower() == "1ao7" else 1
            return {
                "pdb_id": pdb_id.lower(),
                "assembly_count": count,
                "written_paths": [],
                "errors": [],
            }

        monkeypatch.setattr(
            "histo_pdbe_fetch.core.fetch_and_write_pdb_assemblies", mock_write_func
        )

        runner = CliRunner()
        result = runner.invoke(main, ["--output", str(tmp_path), "1ao7", "1bak"])

        assert result.exit_code == 0
        assert "1ao7" in result.output
        assert "1bak" in result.output
        assert "2 PDBs, 3 assemblies written" in result.output

    def test_cli_refresh_flag(self, tmp_path: Path, monkeypatch) -> None:
        """CLI passes --refresh flag to PDBeFetcher."""
        refresh_values = []

        class MockPDBeFetcher:
            def __init__(self, cache_dir, refresh):
                refresh_values.append(refresh)

            def run(self, pdb_ids, output_dir):
                return {
                    "pdb_results": [],
                    "total_assemblies_written": 0,
                    "total_pdbs_processed": 0,
                }

        monkeypatch.setattr("histo_pdbe_fetch.cli.PDBeFetcher", MockPDBeFetcher)

        runner = CliRunner()
        runner.invoke(main, ["--output", str(tmp_path), "--refresh", "1ao7"])

        assert refresh_values == [True]

    def test_cli_cache_dir_option(self, tmp_path: Path, monkeypatch) -> None:
        """CLI passes --cache-dir option to PDBeFetcher."""
        cache_dirs_used = []

        original_init = __import__('histo_pdbe_fetch.core', fromlist=['PDBeFetcher']).PDBeFetcher.__init__

        def mock_init(self, cache_dir, refresh):
            cache_dirs_used.append(cache_dir)
            original_init(self, cache_dir, refresh)

        monkeypatch.setattr("histo_pdbe_fetch.core.PDBeFetcher.__init__", mock_init)

        custom_cache = tmp_path / "my_cache"
        runner = CliRunner()
        runner.invoke(
            main, ["--output", str(tmp_path), "--cache-dir", str(custom_cache), "1ao7"]
        )

        assert cache_dirs_used == [Path(custom_cache)]

    def test_cli_output_creates_directory(self, tmp_path: Path, monkeypatch) -> None:
        """CLI creates output directory if it doesn't exist."""
        def mock_write_func(pdb_id: str, output_dir: Path, cache_dir: Path, refresh: bool):
            return {
                "pdb_id": pdb_id.upper(),
                "assembly_count": 0,
                "written_paths": [],
                "errors": [],
            }

        monkeypatch.setattr(
            "histo_pdbe_fetch.core.fetch_and_write_pdb_assemblies", mock_write_func
        )

        output_dir = tmp_path / "nested" / "output" / "dir"
        runner = CliRunner()
        result = runner.invoke(main, ["--output", str(output_dir), "1ao7"])

        assert result.exit_code == 0
        assert output_dir.exists()

    def test_cli_shows_summary_table(self, tmp_path: Path, monkeypatch) -> None:
        """CLI displays summary table with results."""
        def mock_write_func(pdb_id: str, output_dir: Path, cache_dir: Path, refresh: bool):
            counts = {"1ao7": 2, "1bak": 1, "1a0o": 0}
            count = counts.get(pdb_id.lower(), 0)
            return {
                "pdb_id": pdb_id.lower(),
                "assembly_count": count,
                "written_paths": [],
                "errors": [] if count > 0 else ["404"],
            }

        monkeypatch.setattr(
            "histo_pdbe_fetch.core.fetch_and_write_pdb_assemblies", mock_write_func
        )

        runner = CliRunner()
        result = runner.invoke(main, ["--output", str(tmp_path), "1ao7", "1bak", "1a0o"])

        assert result.exit_code == 0
        # Table should contain PDB ids and assembly counts
        assert "1ao7" in result.output
        assert "1bak" in result.output
        assert "1a0o" in result.output
