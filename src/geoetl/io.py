"""Readers and writers for the formats the pipeline supports.

PostGIS and AGOL sinks are adapters behind optional extras so the core
framework (and its test suite) has no heavy dependencies. They fail with a
clear install hint rather than an ImportError traceback.
"""

from __future__ import annotations

import os
from pathlib import Path

import geopandas as gpd
import pandas as pd

from geoetl.config import SinkConfig, SourceConfig


class SinkError(RuntimeError):
    pass


def read_source(cfg: SourceConfig) -> gpd.GeoDataFrame:
    path = Path(cfg.path)
    if not path.exists():
        raise FileNotFoundError(f"source not found: {path}")

    if cfg.format == "csv":
        df = pd.read_csv(path)
        missing = [f for f in (cfg.x_field, cfg.y_field) if f not in df.columns]
        if missing:
            raise ValueError(f"{path}: csv missing coordinate field(s) {missing}")
        return gpd.GeoDataFrame(
            df,
            geometry=gpd.points_from_xy(df[cfg.x_field], df[cfg.y_field]),
            crs=cfg.crs,
        )
    if cfg.format in {"geojson", "shapefile"}:
        return gpd.read_file(path)
    if cfg.format == "gpkg":
        return gpd.read_file(path, layer=cfg.layer)
    if cfg.format == "parquet":
        return gpd.read_parquet(path)
    raise ValueError(f"unsupported source format: {cfg.format}")


def write_sink(gdf: gpd.GeoDataFrame, cfg: SinkConfig) -> str:
    """Write the frame to the configured sink; returns a human-readable destination."""
    if cfg.format in {"gpkg", "geojson", "parquet"}:
        out = Path(cfg.path)
        out.parent.mkdir(parents=True, exist_ok=True)
        if cfg.format == "gpkg":
            gdf.to_file(out, layer=cfg.layer or "output", driver="GPKG")
        elif cfg.format == "geojson":
            gdf.to_file(out, driver="GeoJSON")
        else:
            gdf.to_parquet(out)
        return str(out)

    if cfg.format == "postgis":
        return _write_postgis(gdf, cfg)
    if cfg.format == "agol":
        return _write_agol(gdf, cfg)
    raise ValueError(f"unsupported sink format: {cfg.format}")


def _write_postgis(gdf: gpd.GeoDataFrame, cfg: SinkConfig) -> str:
    try:
        from sqlalchemy import create_engine
    except ImportError as exc:  # pragma: no cover - exercised only without extra
        raise SinkError("PostGIS sink requires: pip install 'geoetl[postgis]'") from exc

    dsn = os.environ.get("GEOETL_PG_DSN")
    if not dsn:
        raise SinkError("set GEOETL_PG_DSN (e.g. postgresql+psycopg://user:pw@host/db)")
    table = cfg.layer or "geoetl_output"
    engine = create_engine(dsn)
    gdf.to_postgis(table, engine, if_exists="replace", index=False)
    return f"postgis://{table}"


def _write_agol(gdf: gpd.GeoDataFrame, cfg: SinkConfig) -> str:
    try:
        from arcgis.gis import GIS
    except ImportError as exc:  # pragma: no cover - exercised only without extra
        raise SinkError("AGOL sink requires: pip install 'geoetl[agol]'") from exc

    url = os.environ.get("AGOL_URL", "https://www.arcgis.com")
    user, pw = os.environ.get("AGOL_USER"), os.environ.get("AGOL_PASSWORD")
    if not (user and pw):
        raise SinkError("set AGOL_USER and AGOL_PASSWORD in the environment")
    gis = GIS(url, user, pw)
    sdf = pd.DataFrame.spatial.from_geodataframe(gdf)  # type: ignore[attr-defined]
    item = sdf.spatial.to_featurelayer(cfg.layer or "geoetl_output", gis=gis)
    return item.homepage
