"""Cleaning stage: geometry repair, deduplication, field standardization.

Every function takes and returns a GeoDataFrame and reports what it changed
through a CleanLog, so pipeline runs are auditable — "the pipeline dropped
14 rows" is an answer; "the pipeline did something" is not.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import geopandas as gpd
import numpy as np
import shapely
from shapely.validation import make_valid


@dataclass
class CleanLog:
    repaired_geometries: int = 0
    dropped_empty: int = 0
    dropped_duplicates: int = 0
    renamed_fields: dict[str, str] = field(default_factory=dict)

    def summary(self) -> str:
        return (
            f"repaired={self.repaired_geometries} dropped_empty={self.dropped_empty} "
            f"dropped_duplicates={self.dropped_duplicates} renamed={len(self.renamed_fields)}"
        )


_SNAKE_RE = re.compile(r"[^0-9a-zA-Z]+")


def to_snake_case(name: str) -> str:
    """Normalize a field name: 'Facility Name ' -> 'facility_name'."""
    name = _SNAKE_RE.sub("_", name.strip())
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    return name.strip("_").lower()


def standardize_fields(gdf: gpd.GeoDataFrame, log: CleanLog) -> gpd.GeoDataFrame:
    """Rename all non-geometry columns to snake_case; collisions raise."""
    geom_col = gdf.geometry.name
    mapping = {c: to_snake_case(c) for c in gdf.columns if c != geom_col}
    renamed = {old: new for old, new in mapping.items() if old != new}
    targets = list(mapping.values())
    dupes = {t for t in targets if targets.count(t) > 1}
    if dupes:
        raise ValueError(f"field standardization would collide on: {sorted(dupes)}")
    log.renamed_fields.update(renamed)
    return gdf.rename(columns=mapping)


def repair_geometries(gdf: gpd.GeoDataFrame, log: CleanLog) -> gpd.GeoDataFrame:
    """Fix invalid geometries with make_valid; drop rows left empty/null.

    make_valid (GEOS) is preferred over the buffer(0) folk remedy: it
    preserves all geometry where possible and never silently collapses
    polygons to nothing without us noticing — we count what we drop.
    """
    gdf = gdf.copy()
    geoms = np.asarray(gdf.geometry.array, dtype=object)
    missing = shapely.is_missing(geoms)
    empty = missing | shapely.is_empty(geoms)
    invalid = ~shapely.is_valid(geoms) & ~empty
    if invalid.any():
        gdf.loc[invalid, gdf.geometry.name] = gdf.loc[invalid].geometry.apply(make_valid)
        log.repaired_geometries = int(invalid.sum())

    log.dropped_empty = int(empty.sum())
    return gdf.loc[~empty]


def drop_duplicates(
    gdf: gpd.GeoDataFrame, log: CleanLog, subset: list[str] | None = None
) -> gpd.GeoDataFrame:
    """Drop duplicate rows; geometry participates via WKB so equal shapes match."""
    gdf = gdf.copy()
    wkb = gdf.geometry.to_wkb()
    key_cols = subset if subset else [c for c in gdf.columns if c != gdf.geometry.name]
    keys = gdf[key_cols].assign(_wkb=wkb)
    keep = ~keys.duplicated()
    log.dropped_duplicates = int((~keep).sum())
    return gdf.loc[keep]


def run_clean(gdf: gpd.GeoDataFrame, options: dict) -> tuple[gpd.GeoDataFrame, CleanLog]:
    """Run the cleaning stage per config: standardize -> repair -> dedupe."""
    log = CleanLog()
    if options.get("standardize_fields", True):
        gdf = standardize_fields(gdf, log)
    if options.get("repair_geometries", True):
        gdf = repair_geometries(gdf, log)
    if options.get("drop_duplicates", True):
        gdf = drop_duplicates(gdf, log, subset=options.get("duplicate_subset"))
    return gdf, log
