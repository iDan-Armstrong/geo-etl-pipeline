"""Transform stage: a small registry of named, config-drivable operations.

Adding a transform = writing one function and registering it. The registry
pattern keeps the pipeline core closed to modification but open to
extension, and gives config authors an exact list of what they may call.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import geopandas as gpd
import numpy as np

TransformFunc = Callable[..., gpd.GeoDataFrame]
_REGISTRY: dict[str, TransformFunc] = {}


def register(name: str) -> Callable[[TransformFunc], TransformFunc]:
    def deco(fn: TransformFunc) -> TransformFunc:
        if name in _REGISTRY:
            raise ValueError(f"transform {name!r} already registered")
        _REGISTRY[name] = fn
        return fn

    return deco


def available_transforms() -> list[str]:
    return sorted(_REGISTRY)


def apply_transforms(gdf: gpd.GeoDataFrame, steps: list[dict[str, Any]]) -> gpd.GeoDataFrame:
    """Apply configured transform steps in order.

    Each step is ``{op: <name>, **params}``. Unknown ops fail fast with the
    list of valid ones.
    """
    for step in steps:
        step = dict(step)
        op = step.pop("op", None)
        fn = _REGISTRY.get(op)
        if fn is None:
            raise ValueError(f"unknown transform {op!r}; available: {available_transforms()}")
        gdf = fn(gdf, **step)
    return gdf


@register("reproject")
def reproject(gdf: gpd.GeoDataFrame, crs: str) -> gpd.GeoDataFrame:
    if gdf.crs is None:
        raise ValueError("cannot reproject a frame with no CRS; set one at the source")
    return gdf.to_crs(crs)


@register("filter")
def filter_rows(gdf: gpd.GeoDataFrame, query: str) -> gpd.GeoDataFrame:
    """Pandas-query filter, e.g. ``query: "status == 'active'"``."""
    return gdf.query(query)


@register("buffer")
def buffer(gdf: gpd.GeoDataFrame, distance: float) -> gpd.GeoDataFrame:
    """Buffer in the frame's CRS units. Refuses geographic CRS: a degree is
    not a distance, and silently buffering by degrees is a classic data bug."""
    if gdf.crs is not None and gdf.crs.is_geographic:
        raise ValueError(
            f"buffer in a geographic CRS ({gdf.crs}) would use degrees; reproject first"
        )
    out = gdf.copy()
    out[out.geometry.name] = out.geometry.buffer(distance)
    return out


@register("centroid")
def centroid(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    out = gdf.copy()
    out[out.geometry.name] = out.geometry.centroid
    return out


@register("spatial_join")
def spatial_join(
    gdf: gpd.GeoDataFrame,
    right_path: str,
    fields: list[str],
    how: str = "left",
    predicate: str = "intersects",
) -> gpd.GeoDataFrame:
    """Join attributes from another layer (e.g. tag points with admin areas)."""
    right = gpd.read_file(right_path)
    if right.crs != gdf.crs:
        right = right.to_crs(gdf.crs)
    right = right[[*fields, right.geometry.name]]
    joined = gpd.sjoin(gdf, right, how=how, predicate=predicate)
    return joined.drop(columns=[c for c in ("index_right",) if c in joined.columns])


@register("add_area")
def add_area(gdf: gpd.GeoDataFrame, field: str = "area_sqkm") -> gpd.GeoDataFrame:
    """Planar area in km²; refuses geographic CRS for the same reason as buffer."""
    if gdf.crs is not None and gdf.crs.is_geographic:
        raise ValueError(f"area in a geographic CRS ({gdf.crs}) is meaningless; reproject first")
    out = gdf.copy()
    out[field] = out.geometry.area / 1_000_000.0
    return out


@register("zscore")
def zscore(gdf: gpd.GeoDataFrame, field: str, out_field: str | None = None) -> gpd.GeoDataFrame:
    """Standardize a numeric field (NumPy), e.g. for symbology or outlier review."""
    out = gdf.copy()
    values = out[field].astype(float).to_numpy()
    std = np.nanstd(values)
    if std == 0 or np.isnan(std):
        raise ValueError(f"zscore: field {field!r} has zero variance")
    out[out_field or f"{field}_z"] = (values - np.nanmean(values)) / std
    return out
