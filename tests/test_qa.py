from __future__ import annotations

import geopandas as gpd
import pytest
from shapely.geometry import Point

from geoetl.qa import QARule, run_qa


@pytest.fixture
def gdf() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "facility_id": [1, 2, 2, 4],
            "name": ["A", None, "C", "D"],
            "ftype": ["clinic", "clinic", "spaceport", "hospital"],
            "beds": [10, 20, -5, 9000],
        },
        geometry=[Point(0, 0), Point(1, 1), Point(2, 2), Point(3, 3)],
        crs="EPSG:4326",
    )


def test_unknown_rule_kind_raises() -> None:
    with pytest.raises(ValueError, match="unknown QA rule"):
        QARule.from_config({"kind": "psychic_check"})


def test_not_null(gdf: gpd.GeoDataFrame) -> None:
    report = run_qa(gdf, [{"kind": "not_null", "fields": ["name"]}])
    assert not report.passed
    assert list(report.failing_index) == [1]


def test_not_null_missing_field_fails_all_rows(gdf: gpd.GeoDataFrame) -> None:
    report = run_qa(gdf, [{"kind": "not_null", "fields": ["nope"]}])
    assert len(report.failing_index) == len(gdf)


def test_unique(gdf: gpd.GeoDataFrame) -> None:
    report = run_qa(gdf, [{"kind": "unique", "field": "facility_id"}])
    assert sorted(report.failing_index) == [1, 2]


def test_in_set(gdf: gpd.GeoDataFrame) -> None:
    report = run_qa(gdf, [{"kind": "in_set", "field": "ftype", "values": ["clinic", "hospital"]}])
    assert list(report.failing_index) == [2]


def test_range(gdf: gpd.GeoDataFrame) -> None:
    report = run_qa(gdf, [{"kind": "range", "field": "beds", "min": 0, "max": 500}])
    assert sorted(report.failing_index) == [2, 3]


def test_within_bounds_catches_null_island() -> None:
    gdf = gpd.GeoDataFrame(
        {"id": [1, 2]}, geometry=[Point(0, 0), Point(-77, 4.5)], crs="EPSG:4326"
    )
    report = run_qa(
        gdf,
        [{"kind": "within_bounds", "minx": -78, "miny": 4, "maxx": -76, "maxy": 5}],
    )
    assert list(report.failing_index) == [0]


def test_report_aggregates_and_renders(gdf: gpd.GeoDataFrame) -> None:
    report = run_qa(
        gdf,
        [
            {"kind": "not_null", "fields": ["name"]},
            {"kind": "unique", "field": "facility_id"},
            {"kind": "geometry_valid"},
        ],
    )
    assert sorted(report.failing_index) == [1, 2]  # union across rules
    md = report.to_markdown()
    assert "FAIL" in md and "geometry_valid" in md


def test_all_pass(gdf: gpd.GeoDataFrame) -> None:
    report = run_qa(gdf, [{"kind": "geometry_valid"}])
    assert report.passed
    assert "PASS" in report.to_markdown()
