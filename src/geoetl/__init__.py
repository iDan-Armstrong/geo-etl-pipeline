"""geoetl: config-driven geospatial ETL framework.

Pipelines are declared in YAML (see ``examples/``) and executed by
:class:`geoetl.pipeline.Pipeline`. Each stage — read, clean, transform,
QA, load — is a plain function over a GeoDataFrame, so every stage is
unit-testable without any Esri or database dependency.
"""

from geoetl.config import PipelineConfig, load_config
from geoetl.pipeline import Pipeline, PipelineResult
from geoetl.qa import QAReport, QARule

__all__ = [
    "Pipeline",
    "PipelineConfig",
    "PipelineResult",
    "QAReport",
    "QARule",
    "load_config",
]

__version__ = "0.3.0"
