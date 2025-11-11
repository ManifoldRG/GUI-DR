"""
UI Injection Module - Generates JavaScript code for injecting UI modifications.
Supports 3 types: zoom, dense info, and style variants.
"""
from typing import Dict, Any, Optional
from .templates import STYLE_CSS_MAP
from .generator import generate_style_js, COMMON_BASE_CSS
from .zoom import generate_zoom_js
from .dense_info import generate_dense_info_js
from .config import UIModificationConfig


def generate_injection_js(
    params: dict,
    config: Optional[UIModificationConfig] = None,
    llm_texts: Optional[Dict[str, list]] = None,
    target_element_text: Optional[str] = None
) -> str:
    """Generate JavaScript code for injecting UI modifications.
    
    Args:
        params: UI style parameters (for Type 3)
        config: UI modification configuration
        llm_texts: LLM-generated texts for Type 2 (dense info)
        target_element_text: Text content of target element (required for Type 2)
    
    Returns:
        Complete JavaScript injection code
    """
    if config is None:
        config = UIModificationConfig()  # Default: only style variants enabled
    
    # Type 3: Style variants (existing logic)
    style_js_body = ""
    if config.enable_style_variants:
        style = params.get('designStyle', 'modern_minimal')
        style_css = STYLE_CSS_MAP.get(style, STYLE_CSS_MAP['modern_minimal'])
        style_js_full = generate_style_js(params, COMMON_BASE_CSS, style_css)
        # Extract body from function (remove wrapper)
        style_js_body = _extract_function_body(style_js_full)
    
    # Type 1: Zoom
    zoom_js = generate_zoom_js() if config.enable_zoom else ""
    
    # Type 2: Dense info
    dense_info_js = ""
    if config.enable_dense_info:
        dense_info_js = generate_dense_info_js(
            llm_texts=llm_texts,
            target_element_text=target_element_text
        )
    
    # Combine all types
    config_dict = config.to_dict()
    
    # Build the complete injection function
    parts = []
    parts.append(f"(params) => {{")
    parts.append(f"    // Merge config into params")
    parts.append(f"    Object.assign(params, {_format_config_for_js(config_dict)});")
    parts.append("")
    
    if style_js_body:
        parts.append("    // Type 3: Style variants")
        # Indent the body
        indented_body = "\n".join("    " + line if line.strip() else line 
                                  for line in style_js_body.split("\n"))
        parts.append(indented_body)
        parts.append("")
    
    if zoom_js:
        parts.append("    // Type 1: Zoom")
        # Indent the body
        indented_zoom = "\n".join("    " + line if line.strip() else line 
                                  for line in zoom_js.split("\n"))
        parts.append(indented_zoom)
        parts.append("")
    
    if dense_info_js:
        parts.append("    // Type 2: Dense info")
        # Indent the body
        indented_dense = "\n".join("    " + line if line.strip() else line 
                                  for line in dense_info_js.split("\n"))
        parts.append(indented_dense)
        parts.append("")
    
    parts.append("}")
    
    return "\n".join(parts)


def _extract_function_body(js_function: str) -> str:
    """Extract function body from JavaScript function string."""
    # Remove function wrapper: (params) => { ... }
    js_function = js_function.strip()
    if js_function.startswith("(params) => {"):
        # Find first { and last }
        start = js_function.find("{") + 1
        end = js_function.rfind("}")
        if start > 0 and end > start:
            body = js_function[start:end].strip()
            # Remove outer wrapper if it's another function
            if body.startswith("(params) => {"):
                return _extract_function_body(body)
            return body
    return js_function


def _format_config_for_js(config_dict: Dict[str, Any]) -> str:
    """Format config dictionary for JavaScript."""
    items = []
    for key, value in config_dict.items():
        if isinstance(value, bool):
            items.append(f'{key}: {str(value).lower()}')
        elif isinstance(value, (int, float)):
            items.append(f'{key}: {value}')
        else:
            items.append(f'{key}: "{value}"')
    return '{' + ', '.join(items) + '}'
