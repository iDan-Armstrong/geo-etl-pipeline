"""Pipeline orchestration: read -> clean -> transform -> QA -> load."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd

from geoetl.clean import CleanLog, run_clean
from geoetl.config import PipelineConfig
from geoetl.io import read_source, write_sink
from geoetl.qa import QAReport, run_qa
from geoetl.transform import apply_transforms

log = logging.getLogger("geoetl")


class QAGateFailed(RuntimeError):
    """Raised when QA fails and the pipeline is configured to abort."""

    def __init__(self, report: QAReport):
        self.report = report
        super().__init__(
            f"QA failed: {len(report.failing_index)} of {report.total_rows} rows "
            "violate one or more rules (qa.on_fail=abort)"
        )


@dataclass
class PipelineResult:
    rows_in: int
    rows_out: int
    destination: str
    clean_log: CleanLog
    qa_report: QAReport
    quarantined: int
    elapsed_s: float


class Pipeline:
    def __init__(self, config: PipelineConfig):
        self.config = config

    def run(self, qa_report_path: str | Path | None = None) -> PipelineResult:
        t0 = time.perf_counter()
        cfg = self.config
        log.info("pipeline %s: reading %s", cfg.name, cfg.source.path)
        gdf = read_source(cfg.source)
        rows_in = len(gdf)

        gdf, clean_log = run_clean(gdf, cfg.clean)
        log.info("clean: %s", clean_log.summary())

        if cfg.target_crs:
            gdf = gdf.to_crs(cfg.target_crs) if gdf.crs else gdf.set_crs(cfg.target_crs)

        gdf = apply_transforms(gdf, cfg.transforms)

        report = run_qa(gdf, cfg.qa.rules)
        if qa_report_path:
            qa_report_path = Path(qa_report_path)
            qa_report_path.parent.mkdir(parents=True, exist_ok=True)
            qa_report_path.write_text(report.to_markdown())
        quarantined = 0
        if not report.passed:
            if cfg.qa.on_fail == "abort":
                raise QAGateFailed(report)
            if cfg.qa.on_fail == "quarantine":
                failing = report.failing_index
                quarantined = len(failing)
                self._write_quarantine(gdf.loc[gdf.index.isin(failing)])
                gdf = gdf.loc[~gdf.index.isin(failing)]
                log.warning("quarantined %d failing rows", quarantined)
            else:
                log.warning("QA failures present; continuing (qa.on_fail=warn)")

        destination = write_sink(gdf, cfg.sink)
        elapsed = time.perf_counter() - t0
        log.info("pipeline %s: %d -> %d rows -> %s (%.2fs)",
                 cfg.name, rows_in, len(gdf), destination, elapsed)
        return PipelineResult(
            rows_in=rows_in,
            rows_out=len(gdf),
            destination=destination,
            clean_log=clean_log,
            qa_report=report,
            quarantined=quarantined,
            elapsed_s=elapsed,
        )

    def _write_quarantine(self, failing: gpd.GeoDataFrame) -> None:
        sink_path = self.config.sink.path
        base = Path(sink_path).with_suffix("") if sink_path else Path(self.config.name)
        out = base.parent / f"{base.name}_quarantine.geojson"
        out.parent.mkdir(parents=True, exist_ok=True)
        failing.to_file(out, driver="GeoJSON")
        log.warning("quarantine written to %s", out)
