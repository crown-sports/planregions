"""Region geometry and explicit semantic adapters for floor plans."""

from .compare import compare_regions
from .comparison_view import render_comparison_html
from .config import RegionConfig
from .domain import RegionResult
from .pipeline import RegionPipeline

__all__ = [
    "RegionConfig",
    "RegionPipeline",
    "RegionResult",
    "compare_regions",
    "render_comparison_html",
]
__version__ = "0.3.0"
