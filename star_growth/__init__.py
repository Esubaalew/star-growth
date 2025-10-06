"""star_growth - generate scrolling GitHub star growth videos."""

__version__ = "0.2.0"

from .config import StarsAnimationConfig
from .generator import generate_scrolling_stars

__all__ = ["StarsAnimationConfig", "generate_scrolling_stars", "__version__"]
