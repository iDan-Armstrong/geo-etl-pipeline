"""QA stage: declarative rules evaluated against the frame, producing a report.

The QA gate is the difference between a script and a pipeline. Rules are
data (config), results are data (report), and the pipeline decides what to
do about failures per config: abort, warn, or quarantine failing rows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import geopandas as gpd
import pandas as pd


@dataclass(frozen=True)
class QARule:
    """One declarative check. ``kind`` selects the evaluator."""

    kind: str
    params: dict[str, Any]

    @classmethod
    def from_config(cls, raw: dict[str, Any]) -> QARule:
        raw = dict(raw)
        kind = raw.pop("kind", None)
        if kind not in _EVALUATORS:
            raise ValueError(f"unknown QA rule kind {kind!r}; available: {sorted(_EVALUATORS)}")
        return cls(kind=kind, params=raw)


@dataclass
class RuleResult:
    rule: QARule
    failing: pd.Index
    detail: str

    @property
    def passed(self) -> bool:
        return len(self.failing) == 0


@dataclass
class QAReport:
    total_rows: int
    results: list[RuleResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def failing_index(self) -> pd.Index:
        idx: pd.Index = pd.Index([])
        for r in self.results:
            idx = idx.union(r.failing)
        return idx

    def to_markdown(self) -> str:
        lines = [
            "# QA report",
            "",
            f"Rows checked: **{self.total_rows}** — "
            + ("**PASS**" if self.passed else f"**FAIL** ({len(self.failing_index)} rows)"),
            "",
            "| rule | result | failing rows | detail |",
            "|---|---|---:|---|",
        ]
        for r in self.results:
            status = "pass" if r.passed else "FAIL"
            lines.append(f"| {r.rule.kind} | {status} | {len(r.failing)} | {r.detail} |")
        return "\n".join(lines) + "\n"


def _eval_not_null(gdf: gpd.GeoDataFrame, fields: list[str]) -> tuple[pd.Index, str]:
    missing = [f for f in fields if f not in gdf.columns]
    if missing:
        return gdf.index, f"field(s) not present: {missing}"
    mask = gdf[fields].isna().any(axis=1)
    return gdf.index[mask], f"null check on {fields}"


def _eval_unique(gdf: gpd.GeoDataFrame, field: str) -> tuple[pd.Index, str]:
    if field not in gdf.columns:
        return gdf.index, f"field not present: {field!r}"
    mask = gdf[field].duplicated(keep=False)
    return gdf.index[mask], f"uniqueness of {field!r}"


def _eval_in_set(gdf: gpd.GeoDataFrame, field: str, values: list[Any]) -> tuple[pd.Index, str]:
    if field not in gdf.columns:
        return gdf.index, f"field not present: {field!r}"
    mask = ~gdf[field].isin(values)
    return gdf.index[mask], f"{field!r} within domain ({len(values)} values)"


def _eval_range(
    gdf: gpd.GeoDataFrame,
    field: str,
    min: float | None = None,  # noqa: A002 - config-facing name
    max: float | None = None,  # noqa: A002
) -> tuple[pd.Index, str]:
    if field not in gdf.columns:
        return gdf.index, f"field not present: {field!r}"
    series = pd.to_numeric(gdf[field], errors="coerce")
    mask = series.isna()
    if min is not None:
        mask |= series < min
    if max is not None:
        mask |= series > max
    return gdf.index[mask], f"{field!r} in [{min}, {max}]"


def _eval_geometry_valid(gdf: gpd.GeoDataFrame) -> tuple[pd.Index, str]:
    mask = gdf.geometry.isna() | gdf.geometry.is_empty | ~gdf.geometry.is_valid
    return gdf.index[mask], "geometries valid and non-empty"


def _eval_geometry_type(gdf: gpd.GeoDataFrame, types: list[str]) -> tuple[pd.Index, str]:
    mask = ~gdf.geometry.geom_type.isin(types)
    return gdf.index[mask], f"geometry type in {types}"


def _eval_within_bounds(
    gdf: gpd.GeoDataFrame, minx: float, miny: float, maxx: float, maxy: float
) -> tuple[pd.Index, str]:
    """Catch the classic swapped/zeroed coordinate bugs (null island, lat/lon flips)."""
    b = gdf.geometry.bounds
    mask = (b.minx < minx) | (b.miny < miny) | (b.maxx > maxx) | (b.maxy > maxy)
    mask |= gdf.geometry.isna()
    return gdf.index[mask], f"within bbox ({minx}, {miny}, {maxx}, {maxy})"


_EVALUATORS = {
    "not_null": _eval_not_null,
    "unique": _eval_unique,
    "in_set": _eval_in_set,
    "range": _eval_range,
    "geometry_valid": _eval_geometry_valid,
    "geometry_type": _eval_geometry_type,
    "within_bounds": _eval_within_bounds,
}


def run_qa(gdf: gpd.GeoDataFrame, rules: list[dict[str, Any]]) -> QAReport:
    report = QAReport(total_rows=len(gdf))
    for raw in rules:
        rule = QARule.from_config(raw)
        failing, detail = _EVALUATORS[rule.kind](gdf, **rule.params)
        report.results.append(RuleResult(rule=rule, failing=failing, detail=detail))
    return report
