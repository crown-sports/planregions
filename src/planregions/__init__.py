"""Region geometry and explicit semantic adapters for floor plans."""

from .config import RegionConfig
from .domain import RegionResult
from .pipeline import RegionPipeline

__all__ = ["RegionConfig", "RegionPipeline", "RegionResult"]
__version__ = "0.1.1"
