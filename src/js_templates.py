"""
JavaScript Templates - Style-specific CSS fragments for UI injection.
Extracted from ui_injection.py for better maintainability.
"""

# Style-specific CSS fragments
NEOBRUTALISM_CSS = """
                    border: {btnBorderWidth}px solid {btnBorderColor} !important;
                    border-radius: {btnBorderRadius}px !important;
                    box-shadow: {btnShadowX}px {btnShadowY}px {btnShadowBlur}px {btnShadowColor} !important;
                    text-transform: uppercase !important;
                    letter-spacing: 0.1em !important;
"""

GLASSMORPHISM_CSS = """
                    border: {btnBorderWidth}px solid {btnBorderColor} !important;
                    border-radius: {btnBorderRadius}px !important;
                    backdrop-filter: blur({btnBackdropBlur}px) !important;
                    box-shadow: {btnShadowX}px {btnShadowY}px {btnShadowBlur}px {btnShadowColor} !important;
                    background: linear-gradient(135deg, rgba(255,255,255,0.1), rgba(255,255,255,0)) !important;
"""

NEUMORPHISM_CSS = """
                    border: {btnBorderWidth}px solid transparent !important;
                    border-radius: {btnBorderRadius}px !important;
                    box-shadow: {btnShadowLight}, {btnShadowDark} !important;
                    background: {btnBg} !important;
"""

RETRO_CSS = """
                    border: {btnBorderWidth}px solid {btnBorderColor} !important;
                    border-radius: {btnBorderRadius}px !important;
                    box-shadow: {btnShadowX}px {btnShadowY}px {btnShadowBlur}px {btnShadowColor} !important;
                    background: linear-gradient(135deg, {btnBg}, {btnBg}dd) !important;
"""

DARK_MODE_CSS = """
                    border: {btnBorderWidth}px solid {btnBorderColor} !important;
                    border-radius: {btnBorderRadius}px !important;
                    box-shadow: 0 0 {btnShadowBlur}px {btnShadowColor}, 0 0 {btnShadowBlur}px {btnShadowColor} !important;
                    background: {btnBg} !important;
                    text-shadow: 0 0 10px {btnTextColor} !important;
"""

PASTEL_CSS = """
                    border: {btnBorderWidth}px solid {btnBorderColor} !important;
                    border-radius: {btnBorderRadius}px !important;
                    box-shadow: {btnShadowX}px {btnShadowY}px {btnShadowBlur}px {btnShadowColor} !important;
                    background: linear-gradient(135deg, {btnBg}, {btnBg}ee) !important;
"""

CYBERPUNK_CSS = """
                    border: {btnBorderWidth}px solid {btnBorderColor} !important;
                    border-radius: {btnBorderRadius}px !important;
                    box-shadow: 0 0 {btnShadowBlur}px {btnShadowColor}, inset 0 0 {btnShadowBlur}px {btnShadowColor} !important;
                    background: {btnBg} !important;
                    text-shadow: 0 0 5px {btnTextColor}, 0 0 10px {btnTextColor} !important;
"""

MODERN_CSS = """
                    border: {btnBorderWidth}px solid {btnBorderColor} !important;
                    border-radius: {btnBorderRadius}px !important;
                    box-shadow: {btnShadowX}px {btnShadowY}px {btnShadowBlur}px {btnShadowColor} !important;
                    background: {btnBg} !important;
"""

# Map style names to their CSS templates
STYLE_CSS_MAP = {
    'neobrutalism': NEOBRUTALISM_CSS,
    'glassmorphism': GLASSMORPHISM_CSS,
    'neumorphism': NEUMORPHISM_CSS,
    'retro_vibrant': RETRO_CSS,
    'dark_mode': DARK_MODE_CSS,
    'pastel_dream': PASTEL_CSS,
    'cyberpunk': CYBERPUNK_CSS,
    'modern_minimal': MODERN_CSS,
}

