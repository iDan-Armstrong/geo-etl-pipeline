from __future__ import annotations

import geopandas as gpd
import pytest
from shapely.geometry import Point, Polygon


@pytest.fixture
def points_gdf() -> gpd.GeoDataFrame:
    """Small point frame with known dirt: a duplicate, a null name, a bad domain value."""
    data = {
        "Facility ID": [1, 2, 3, 3, 4],
        "Facility Name": ["Alpha", "Bravo", "Charlie", "Charlie", None],
        "facilityType": ["clinic", "hospital", "clinic", "clinic", "clnic"],
        "Beds": [10, 250, 5, 5, -1],
    }
    geoms = [Point(0.1, 0.1), Point(0.2, 0.2), Point(0.3, 0.3), Point(0.3, 0.3), Point(0.4, 0.4)]
    return gpd.GeoDataFrame(data, geometry=geoms, crs="EPSG:4326")


@pytest.fixture
def bowtie_gdf() -> gpd.GeoDataFrame:
    """One valid square, one invalid self-intersecting (bowtie) polygon, one empty."""
    valid = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    bowtie = Polygon([(0, 0), (1, 1), (1, 0), (0, 1)])
    empty = Polygon()
    return gpd.GeoDataFrame(
        {"name": ["square", "bowtie", "empty"]},
        geometry=[valid, bowtie, empty],
        crs="EPSG:4326",
    )
