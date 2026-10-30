"""End-to-end tests: run the real example pipeline against the bundled data."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import geopandas as gpd
import pytest
import yaml

from geoetl.config import ConfigError, load_config
from geoetl.pipeline import Pipeline, QAGateFailed

REPO = Path(__file__).resolve().parents[1]
EXAMPLE = REPO / "examples" / "facilities_pipeline.yml"


@pytest.fixture
def example_dir(tmp_path: Path) -> Path:
    """Copy the example into a tmp dir so tests never dirty the working tree."""
    shutil.copytree(REPO / "examples", tmp_path / "examples")
    return tmp_path


def _load_example(example_dir: Path):
    cfg = load_config(example_dir / "examples" / "facilities_pipeline.yml")
    # Re-anchor relative paths to the tmp dir
    raw = yaml.safe_load((example_dir / "examples" / "facilities_pipeline.yml").read_text())
    raw["source"]["path"] = str(example_dir / raw["source"]["path"])
    raw["sink"]["path"] = str(example_dir / raw["sink"]["path"])
    for step in raw.get("transforms", []):
        if "right_path" in step:
            step["right_path"] = str(example_dir / step["right_path"])
    patched = example_dir / "pipeline_patched.yml"
    patched.write_text(yaml.safe_dump(raw))
    cfg = load_config(patched)
    return cfg


def test_example_pipeline_end_to_end(example_dir: Path) -> None:
    cfg = _load_example(example_dir)
    result = Pipeline(cfg).run(qa_report_path=example_dir / "qa.md")

    # the bundled dirt must be caught: 3 duplicate rows dropped, dirty rows quarantined
    assert result.clean_log.dropped_duplicates == 3
    assert result.quarantined >= 4  # null name, bad domain, negative beds, null island
    assert result.rows_out == result.rows_in - 3 - result.quarantined

    out = gpd.read_file(cfg.sink.path, layer=cfg.sink.layer)
    assert len(out) == result.rows_out
    assert out.crs.to_epsg() == 3857
    assert {"facility_name", "district", "beds_z"} <= set(out.columns)

    quarantine = Path(cfg.sink.path).parent / "facilities_clean_quarantine.geojson"
    assert quarantine.exists()
    assert (example_dir / "qa.md").exists()


def test_abort_mode_raises(example_dir: Path) -> None:
    cfg = _load_example(example_dir)
    object.__setattr__(cfg.qa, "on_fail", "abort")
    with pytest.raises(QAGateFailed) as exc_info:
        Pipeline(cfg).run()
    assert exc_info.value.report.total_rows > 0


def test_invalid_config_reports_all_errors(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yml"
    bad.write_text(
        yaml.safe_dump(
            {
                "source": {"format": "csv"},  # missing name, path, x/y/crs
                "sink": {"format": "gpkg"},  # missing path
                "qa": {"on_fail": "explode"},
            }
        )
    )
    with pytest.raises(ConfigError) as exc_info:
        load_config(bad)
    msg = str(exc_info.value)
    for needle in ("'name'", "source.path", "x_field", "sink.path", "on_fail"):
        assert needle in msg, f"expected {needle!r} in combined error"


def test_cli_validate_and_transforms() -> None:
    out = subprocess.run(
        [sys.executable, "-m", "geoetl.cli", "validate", str(EXAMPLE)],
        capture_output=True,
        text=True,
        cwd=REPO,
    )
    assert out.returncode == 0, out.stderr
    assert "OK" in out.stdout

    out = subprocess.run(
        [sys.executable, "-m", "geoetl.cli", "transforms"],
        capture_output=True,
        text=True,
        cwd=REPO,
    )
    assert "reproject" in out.stdout
