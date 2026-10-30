from __future__ import annotations

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import Point

from geoetl.transform import apply_transforms, available_transforms


@pytest.fixture
def wgs84_points() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"beds": [10.0, 20.0, 30.0, 100.0]},
        geometry=[Point(-77.0, 4.1), Point(-77.1, 4.2), Point(-77.2, 4.3), Point(-77.3, 4.4)],
        crs="EPSG:4326",
    )


def test_registry_is_populated() -> None:
    assert {"reproject", "buffer", "spatial_join", "zscore"} <= set(available_transforms())


def test_unknown_op_fails_fast(wgs84_points: gpd.GeoDataFrame) -> None:
    with pytest.raises(ValueError, match="unknown transform"):
        apply_transforms(wgs84_points, [{"op": "does_not_exist"}])


def test_reproject(wgs84_points: gpd.GeoDataFrame) -> None:
    out = apply_transforms(wgs84_points, [{"op": "reproject", "crs": "EPSG:3857"}])
    assert out.crs.to_epsg() == 3857
    assert abs(out.geometry.x.iloc[0]) > 1_000_000  # meters now, not degrees


def test_buffer_refuses_geographic_crs(wgs84_points: gpd.GeoDataFrame) -> None:
    with pytest.raises(ValueError, match="degrees"):
        apply_transforms(wgs84_points, [{"op": "buffer", "distance": 100}])


def test_buffer_after_reproject(wgs84_points: gpd.GeoDataFrame) -> None:
    out = apply_transforms(
        wgs84_points,
        [{"op": "reproject", "crs": "EPSG:3857"}, {"op": "buffer", "distance": 100}],
    )
    assert (out.geometry.geom_type == "Polygon").all()


def test_zscore(wgs84_points: gpd.GeoDataFrame) -> None:
    out = apply_transforms(wgs84_points, [{"op": "zscore", "field": "beds"}])
    assert "beds_z" in out.columns
    np.testing.assert_allclose(out["beds_z"].mean(), 0.0, atol=1e-9)


def test_zscore_zero_variance_raises() -> None:
    gdf = gpd.GeoDataFrame(
        {"v": [5.0, 5.0]}, geometry=[Point(0, 0), Point(1, 1)], crs="EPSG:4326"
    )
    with pytest.raises(ValueError, match="zero variance"):
        apply_transforms(gdf, [{"op": "zscore", "field": "v"}])


def test_filter(wgs84_points: gpd.GeoDataFrame) -> None:
    out = apply_transforms(wgs84_points, [{"op": "filter", "query": "beds > 15"}])
    assert len(out) == 3
