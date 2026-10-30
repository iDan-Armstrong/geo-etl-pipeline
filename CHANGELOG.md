# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); versioning follows SemVer.

## [0.3.0] — unreleased
### Added
- `quarantine` QA failure policy: failing rows are written to a reviewable
  GeoJSON while clean rows continue to the sink.
- `zscore` transform (NumPy) for outlier flagging.
- `within_bounds` QA rule to catch null-island and swapped-coordinate rows.

## [0.2.0]
### Added
- PostGIS and ArcGIS Online sinks as optional extras (`geoetl[postgis]`, `geoetl[agol]`).
- `geoetl validate` subcommand; exit codes documented.
### Changed
- Config validation now collects and reports all errors at once.

## [0.1.0]
### Added
- Core pipeline: csv/geojson/gpkg/parquet sources, clean stage with audit log,
  transform registry, declarative QA rules, GeoPackage sink, CLI.
