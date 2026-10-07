"""Region geometry and explicit semantic adapters for floor plans."""

from .compare import compare_regions
from .config import RegionConfig
from .domain import RegionResult
from .pipeline import RegionPipeline

__all__ = ["RegionConfig", "RegionPipeline", "RegionResult", "compare_regions"]
__version__ = "0.2.0"
