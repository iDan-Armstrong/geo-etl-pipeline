from __future__ import annotations

import geopandas as gpd
import pytest
from shapely.geometry import Point

from geoetl.clean import (
    CleanLog,
    drop_duplicates,
    repair_geometries,
    run_clean,
    standardize_fields,
    to_snake_case,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Facility Name", "facility_name"),
        ("facilityType", "facility_type"),
        ("  LON ", "lon"),
        ("Area (sq km)", "area_sq_km"),
        ("already_snake", "already_snake"),
    ],
)
def test_to_snake_case(raw: str, expected: str) -> None:
    assert to_snake_case(raw) == expected


def test_standardize_fields_renames_and_logs(points_gdf: gpd.GeoDataFrame) -> None:
    log = CleanLog()
    out = standardize_fields(points_gdf, log)
    assert "facility_name" in out.columns
    assert "Facility Name" not in out.columns
    assert log.renamed_fields["Facility Name"] == "facility_name"


def test_standardize_fields_collision_raises() -> None:
    gdf = gpd.GeoDataFrame(
        {"My Field": [1], "my field": [2]}, geometry=[Point(0, 0)], crs="EPSG:4326"
    )
    with pytest.raises(ValueError, match="collide"):
        standardize_fields(gdf, CleanLog())


def test_repair_geometries_fixes_bowtie_and_drops_empty(bowtie_gdf: gpd.GeoDataFrame) -> None:
    log = CleanLog()
    out = repair_geometries(bowtie_gdf, log)
    assert log.repaired_geometries == 1
    assert log.dropped_empty == 1
    assert len(out) == 2
    assert out.geometry.is_valid.all()
    # make_valid must preserve area, not collapse the bowtie to nothing
    assert out.loc[out["name"] == "bowtie"].geometry.iloc[0].area > 0


def test_drop_duplicates_counts_geometry(points_gdf: gpd.GeoDataFrame) -> None:
    log = CleanLog()
    out = drop_duplicates(points_gdf, log)
    assert log.dropped_duplicates == 1
    assert len(out) == len(points_gdf) - 1


def test_drop_duplicates_same_attrs_different_geometry_kept() -> None:
    gdf = gpd.GeoDataFrame(
        {"name": ["A", "A"]}, geometry=[Point(0, 0), Point(1, 1)], crs="EPSG:4326"
    )
    out = drop_duplicates(gdf, CleanLog())
    assert len(out) == 2


def test_run_clean_full_stage(points_gdf: gpd.GeoDataFrame) -> None:
    out, log = run_clean(points_gdf, {})
    assert "facility_id" in out.columns
    assert log.dropped_duplicates == 1
    assert len(out) == 4
