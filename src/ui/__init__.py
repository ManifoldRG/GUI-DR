"""
UI modification modules for injecting styles and randomizing UI elements.
"""

from .injection import generate_injection_js
from .generator import generate_style_js, COMMON_BASE_CSS
from .templates import STYLE_CSS_MAP
from .randomization import generate_diverse_ui_params
from .styles_data import COLOR_PALETTES, FONT_COMBINATIONS

__all__ = [
    'generate_injection_js',
    'generate_style_js',
    'COMMON_BASE_CSS',
    'STYLE_CSS_MAP',
    'generate_diverse_ui_params',
    'COLOR_PALETTES',
    'FONT_COMBINATIONS'
]


