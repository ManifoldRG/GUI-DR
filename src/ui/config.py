"""
UI Modification Configuration - Controls which types of UI modifications are enabled.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class UIModificationConfig:
    """Configuration for enabling/disabling different types of UI modifications."""
    
    # Type 1: Precision GUI element understanding (viewport zoom)
    enable_zoom: bool = False
    zoom_level: float = 0.7  # 0.7 (70%), 0.5 (50%), or 0.3 (30%)
    
    # Type 2: Complex, dense information (paraphrase + clone with LLM text)
    enable_dense_info: bool = False
    
    # Type 3: Mixed UI type variants (colors, shapes, styles)
    enable_style_variants: bool = True
    
    def __post_init__(self):
        """Validate configuration values."""
        if self.zoom_level not in [0.7, 0.5, 0.3]:
            raise ValueError(f"zoom_level must be 0.7, 0.5, or 0.3, got {self.zoom_level}")
    
    def to_dict(self) -> dict:
        """Convert config to dictionary for JavaScript injection."""
        return {
            'enableZoom': self.enable_zoom,
            'zoomLevel': self.zoom_level,
            'enableDenseInfo': self.enable_dense_info,
            'enableStyleVariants': self.enable_style_variants,
        }

