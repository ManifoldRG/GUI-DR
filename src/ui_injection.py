"""
UI Injection Module - Generates JavaScript code for injecting UI modifications.
Simplified to use extracted templates and generators.
"""
from js_templates import STYLE_CSS_MAP
from js_generator import generate_style_js, COMMON_BASE_CSS


def generate_injection_js(params: dict) -> str:
    """Generate JavaScript code for injecting UI modifications."""
    style = params.get('designStyle', 'modern_minimal')
    style_css = STYLE_CSS_MAP.get(style, STYLE_CSS_MAP['modern_minimal'])
    return generate_style_js(params, COMMON_BASE_CSS, style_css)
