"""Pipeline configuration: a validated, typed view over a YAML file.

Design decision: configuration is validated *eagerly and completely* at load
time, so a pipeline never fails three stages in with a KeyError. Every
validation error found is reported at once (not just the first), because a
config author fixing a file wants the full list.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

VALID_SOURCE_FORMATS = {"geojson", "gpkg", "csv", "shapefile", "parquet"}
VALID_SINK_FORMATS = {"gpkg", "geojson", "parquet", "postgis", "agol"}
VALID_ON_QA_FAIL = {"abort", "warn", "quarantine"}


class ConfigError(ValueError):
    """Raised when a pipeline config is structurally invalid.

    Carries every problem found, newline-separated, so the author can fix
    the file in one pass.
    """


@dataclass(frozen=True)
class SourceConfig:
    path: str
    format: str
    layer: str | None = None
    x_field: str | None = None  # csv only
    y_field: str | None = None  # csv only
    crs: str | None = None  # csv only; e.g. "EPSG:4326"


@dataclass(frozen=True)
class SinkConfig:
    format: str
    path: str | None = None
    layer: str | None = None
    # postgis / agol sinks read connection details from the environment,
    # never from the config file (12-factor; keeps secrets out of git).


@dataclass(frozen=True)
class QAConfig:
    rules: list[dict[str, Any]] = field(default_factory=list)
    on_fail: str = "abort"


@dataclass(frozen=True)
class PipelineConfig:
    name: str
    source: SourceConfig
    sink: SinkConfig
    target_crs: str | None = None
    clean: dict[str, Any] = field(default_factory=dict)
    transforms: list[dict[str, Any]] = field(default_factory=list)
    qa: QAConfig = field(default_factory=QAConfig)


def _collect_errors(raw: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not raw.get("name"):
        errors.append("'name' is required")

    source = raw.get("source")
    if not isinstance(source, dict):
        errors.append("'source' section is required")
    else:
        if not source.get("path"):
            errors.append("source.path is required")
        fmt = source.get("format")
        if fmt not in VALID_SOURCE_FORMATS:
            errors.append(
                f"source.format must be one of {sorted(VALID_SOURCE_FORMATS)}, got {fmt!r}"
            )
        if fmt == "csv":
            for key in ("x_field", "y_field", "crs"):
                if not source.get(key):
                    errors.append(f"source.{key} is required when source.format is 'csv'")

    sink = raw.get("sink")
    if not isinstance(sink, dict):
        errors.append("'sink' section is required")
    else:
        fmt = sink.get("format")
        if fmt not in VALID_SINK_FORMATS:
            errors.append(f"sink.format must be one of {sorted(VALID_SINK_FORMATS)}, got {fmt!r}")
        if fmt in {"gpkg", "geojson", "parquet"} and not sink.get("path"):
            errors.append(f"sink.path is required for format {fmt!r}")

    qa = raw.get("qa", {})
    if isinstance(qa, dict):
        on_fail = qa.get("on_fail", "abort")
        if on_fail not in VALID_ON_QA_FAIL:
            errors.append(f"qa.on_fail must be one of {sorted(VALID_ON_QA_FAIL)}, got {on_fail!r}")

    return errors


def load_config(path: str | Path) -> PipelineConfig:
    """Load and validate a pipeline YAML file.

    Raises
    ------
    ConfigError
        Listing *every* validation problem found, one per line.
    """
    raw = yaml.safe_load(Path(path).read_text())
    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: top level must be a mapping")

    errors = _collect_errors(raw)
    if errors:
        raise ConfigError(f"{path} is invalid:\n  - " + "\n  - ".join(errors))

    qa_raw = raw.get("qa", {}) or {}
    return PipelineConfig(
        name=raw["name"],
        source=SourceConfig(**raw["source"]),
        sink=SinkConfig(**raw["sink"]),
        target_crs=raw.get("target_crs"),
        clean=raw.get("clean", {}) or {},
        transforms=raw.get("transforms", []) or [],
        qa=QAConfig(rules=qa_raw.get("rules", []) or [], on_fail=qa_raw.get("on_fail", "abort")),
    )
