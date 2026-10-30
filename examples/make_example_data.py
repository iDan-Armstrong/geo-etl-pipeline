"""Generate the bundled example dataset (synthetic, so it carries no license).

A deliberately dirty CSV of ~200 'health facility' points across four
fictional districts, plus a district boundary layer. The dirt is the point:
duplicate rows, a null-island coordinate, out-of-range values, mixed-case
field names, an invalid (bowtie) polygon — everything the pipeline exists
to catch.

Run from the repo root:  python examples/make_example_data.py
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Polygon

HERE = Path(__file__).parent
rng = np.random.default_rng(42)

DISTRICTS = {
    "Northwood": (-77.60, 4.40, -77.20, 4.80),
    "Eastmarsh": (-77.20, 4.40, -76.80, 4.80),
    "Southvale": (-77.60, 4.00, -77.20, 4.40),
    "Westbrook": (-77.20, 4.00, -76.80, 4.40),
}
TYPES = ["clinic", "hospital", "health_post", "pharmacy"]


def make_facilities() -> pd.DataFrame:
    rows = []
    fid = 1000
    for name, (minx, miny, maxx, maxy) in DISTRICTS.items():
        n = int(rng.integers(40, 60))
        xs = rng.uniform(minx + 0.02, maxx - 0.02, n)
        ys = rng.uniform(miny + 0.02, maxy - 0.02, n)
        for x, y in zip(xs, ys, strict=True):
            rows.append(
                {
                    "Facility ID": fid,
                    "Facility Name": f"{name} {rng.choice(['Community', 'District', 'Rural'])}"
                    f" Facility {fid}",
                    "facilityType": rng.choice(TYPES, p=[0.5, 0.1, 0.3, 0.1]),
                    "Beds": int(rng.integers(0, 120)),
                    "LON": round(float(x), 6),
                    "LAT": round(float(y), 6),
                }
            )
            fid += 1
    df = pd.DataFrame(rows)

    # --- deliberate dirt ---
    df = pd.concat([df, df.iloc[[3, 17, 42]]], ignore_index=True)  # exact duplicates
    df.loc[5, ["LON", "LAT"]] = (0.0, 0.0)  # null island
    df.loc[9, "Beds"] = -4  # impossible value
    df.loc[12, "facilityType"] = "clnic"  # typo outside domain
    df.loc[20, "Facility Name"] = None  # missing name
    return df


def make_districts() -> gpd.GeoDataFrame:
    geoms, names = [], []
    for name, (minx, miny, maxx, maxy) in DISTRICTS.items():
        geoms.append(Polygon([(minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy)]))
        names.append(name)
    # one invalid bowtie polygon, to exercise geometry repair downstream
    geoms.append(Polygon([(-76.8, 4.0), (-76.4, 4.4), (-76.4, 4.0), (-76.8, 4.4)]))
    names.append("Bowtie Reserve")
    return gpd.GeoDataFrame({"district": names}, geometry=geoms, crs="EPSG:4326")


if __name__ == "__main__":
    make_facilities().to_csv(HERE / "data" / "facilities_raw.csv", index=False)
    make_districts().to_file(HERE / "data" / "districts.geojson", driver="GeoJSON")
    print("wrote examples/data/facilities_raw.csv and examples/data/districts.geojson")
