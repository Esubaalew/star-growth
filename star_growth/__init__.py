"""star_growth - generate scrolling GitHub star growth videos."""

__version__ = "0.1.1"

from .config import StarsAnimationConfig
from .generator import generate_scrolling_stars

__all__ = ["StarsAnimationConfig", "generate_scrolling_stars", "__version__"]
