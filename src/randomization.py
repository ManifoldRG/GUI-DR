import random
import re
from ui_styles_data import COLOR_PALETTES, FONT_COMBINATIONS


def hex_to_rgb(hex_color):
    """Convert hex color to RGB tuple"""
    if hex_color.startswith('rgba'):
        match = re.search(r'rgba?\((\d+),\s*(\d+),\s*(\d+)', hex_color)
        if match:
            return tuple(int(x) for x in match.groups())
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def get_luminance(rgb):
    """Calculate relative luminance according to WCAG formula"""
    def adjust_channel(channel):
        channel = channel / 255.0
        return channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4
    r, g, b = [adjust_channel(c) for c in rgb]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def get_contrast_ratio(color1, color2):
    """Calculate WCAG contrast ratio between two colors"""
    rgb1 = hex_to_rgb(color1) if isinstance(color1, str) else color1
    rgb2 = hex_to_rgb(color2) if isinstance(color2, str) else color2
    lum1, lum2 = get_luminance(rgb1), get_luminance(rgb2)
    lighter, darker = max(lum1, lum2), min(lum1, lum2)
    return (lighter + 0.05) / (darker + 0.05)


def find_accessible_text_color(bg_color, dark_options, light_options, min_ratio=4.5):
    """Find an accessible text color for the given background"""
    for text_color in dark_options + light_options:
        if get_contrast_ratio(bg_color, text_color) >= min_ratio:
            return text_color
    bg_lum = get_luminance(hex_to_rgb(bg_color) if isinstance(bg_color, str) and '#' in bg_color else (240, 240, 240))
    return light_options[0] if bg_lum < 0.5 else dark_options[0]


def generate_diverse_ui_params():
    """
    Generate highly diverse UI parameters for maximum visual difference.
    Creates dramatic color, font, and style variations while maintaining text overflow prevention.
    """
    style = random.choice(list(COLOR_PALETTES.keys()))
    colors = COLOR_PALETTES[style]
    bg_color = random.choice(colors['backgrounds'])
    primary_color = random.choice(colors['primaries'])
    body_text_color = find_accessible_text_color(bg_color, colors['dark_text'], colors['light_text'])
    btn_text_color = find_accessible_text_color(primary_color, colors['dark_text'], colors['light_text'])
    
    # Get font combination for the selected style
    heading_font, body_font = random.choice(FONT_COMBINATIONS.get(style, FONT_COMBINATIONS['modern_minimal']))
    
    # Base parameters with more dramatic variations
    base_params = {
        'designStyle': style,
        'bgColor': bg_color,
        'primaryColor': primary_color,
        'textColor': body_text_color,
        'headingColor': body_text_color,
        'headingFont': heading_font,
        'bodyFont': body_font,
        # Slightly larger font size variations for more visual impact
        'bodySize': random.choice([14, 15, 16, 17, 18, 19]),
        'headingSize': random.choice([24, 28, 32, 36, 40]),
        # More font weight variations
        'bodyWeight': random.choice([400, 500, 600, 700]),
        'headingWeight': random.choice([600, 700, 800, 900]),
        # Letter spacing with more variation
        'letterSpacing': round(random.uniform(-0.02, 0.03), 3),
        'lineHeight': round(random.uniform(1.3, 1.7), 2),
        'btnBg': primary_color,
        'btnTextColor': btn_text_color,
        'linkColor': primary_color,
        'transitionSpeed': round(random.uniform(0.15, 0.4), 2),
    }
    
    # Style-specific parameters with more dramatic variations
    if style == 'neobrutalism':
        base_params.update({
            'btnBorderWidth': random.randint(4, 8),
            'btnBorderColor': random.choice(colors['borders']),
            'btnBorderRadius': random.choice([0, 2, 4, 8]),
            'btnPaddingX': random.randint(24, 40),
            'btnPaddingY': random.randint(12, 20),
            'btnShadowX': random.randint(6, 12),
            'btnShadowY': random.randint(6, 12),
            'btnShadowBlur': 0,
            'btnShadowColor': '#000000',
            'inputBg': '#FFFFFF',
            'inputTextColor': '#000000',
            'inputBorderWidth': random.randint(3, 6),
            'inputBorderColor': random.choice(colors['borders']),
            'inputBorderRadius': random.choice([0, 2, 4]),
            'inputPaddingX': random.randint(14, 20),
            'inputPaddingY': random.randint(10, 14),
        })
    elif style == 'glassmorphism':
        text_bg = random.choice(colors['solid_backgrounds'])
        text_color = find_accessible_text_color(text_bg, colors['dark_text'], colors['light_text'])
        base_params.update({
            'bgColor': f"linear-gradient({random.randint(0, 360)}deg, {random.choice(['#667EEA', '#764BA2', '#F093FB', '#4FACFE', '#00F2FE', '#43E97B', '#FA709A', '#FEE140', '#FF6B6B', '#4ECDC4'])} 0%, {random.choice(['#764BA2', '#F093FB', '#00F2FE', '#38F9D7', '#4FACFE', '#43E97B', '#FEE140', '#FA709A', '#FF6B6B', '#4ECDC4'])} 100%)",
            'textColor': text_color,
            'headingColor': text_color,
            'textContainerBg': text_bg,
            'btnBorderWidth': random.randint(1, 3),
            'btnBorderColor': 'rgba(255, 255, 255, 0.3)',
            'btnBorderRadius': random.randint(16, 24),
            'btnPaddingX': random.randint(22, 32),
            'btnPaddingY': random.randint(12, 18),
            'btnBackdropBlur': random.randint(15, 25),
            'btnShadowX': 0,
            'btnShadowY': random.randint(8, 12),
            'btnShadowBlur': random.randint(32, 48),
            'btnShadowColor': 'rgba(0, 0, 0, 0.15)',
            'inputBg': text_bg,
            'inputTextColor': text_color,
            'inputBorderWidth': random.randint(1, 2),
            'inputBorderColor': 'rgba(255, 255, 255, 0.3)',
            'inputBorderRadius': random.randint(12, 20),
            'inputPaddingX': random.randint(14, 18),
            'inputPaddingY': random.randint(10, 14),
            'inputBackdropBlur': random.randint(10, 20),
        })
    elif style == 'neumorphism':
        base_params.update({
            'btnBg': bg_color,
            'btnTextColor': body_text_color,
            'btnBorderWidth': 0,
            'btnBorderRadius': random.randint(16, 24),
            'btnPaddingX': random.randint(22, 32),
            'btnPaddingY': random.randint(12, 18),
            'btnShadowLight': f"{random.randint(-8, -4)}px {random.randint(-8, -4)}px {random.randint(16, 20)}px rgba(255, 255, 255, 0.8)",
            'btnShadowDark': f"{random.randint(8, 12)}px {random.randint(8, 12)}px {random.randint(16, 20)}px rgba(0, 0, 0, 0.2)",
            'inputBg': bg_color,
            'inputTextColor': body_text_color,
            'inputBorderWidth': 0,
            'inputBorderRadius': random.randint(12, 20),
            'inputPaddingX': random.randint(14, 18),
            'inputPaddingY': random.randint(10, 14),
            'inputShadowInset': f"inset {random.randint(3, 5)}px {random.randint(3, 5)}px {random.randint(8, 12)}px rgba(0, 0, 0, 0.15)",
        })
    elif style == 'retro_vibrant':
        base_params.update({
            'btnBorderWidth': random.choice([0, 3, 4]),
            'btnBorderColor': random.choice(colors['borders']),
            'btnBorderRadius': random.randint(24, 40),
            'btnPaddingX': random.randint(24, 36),
            'btnPaddingY': random.randint(12, 20),
            'btnShadowX': 0,
            'btnShadowY': random.randint(6, 12),
            'btnShadowBlur': random.randint(16, 24),
            'btnShadowColor': 'rgba(0, 0, 0, 0.25)',
            'inputBg': '#FFFFFF',
            'inputTextColor': colors['dark_text'][0],
            'inputBorderWidth': random.randint(3, 5),
            'inputBorderColor': random.choice(colors['borders']),
            'inputBorderRadius': random.randint(16, 24),
            'inputPaddingX': random.randint(14, 20),
            'inputPaddingY': random.randint(10, 14),
        })
    elif style == 'dark_mode':
        base_params.update({
            'btnBorderWidth': random.choice([0, 2, 3]),
            'btnBorderColor': primary_color,
            'btnBorderRadius': random.randint(8, 16),
            'btnPaddingX': random.randint(20, 32),
            'btnPaddingY': random.randint(12, 18),
            'btnShadowX': 0,
            'btnShadowY': random.randint(4, 8),
            'btnShadowBlur': random.randint(16, 24),
            'btnShadowColor': f"{primary_color}80",
            'inputBg': '#1A1A1A',
            'inputTextColor': body_text_color,
            'inputBorderWidth': random.randint(2, 4),
            'inputBorderColor': primary_color,
            'inputBorderRadius': random.randint(8, 12),
            'inputPaddingX': random.randint(14, 18),
            'inputPaddingY': random.randint(10, 14),
        })
    elif style == 'pastel_dream':
        base_params.update({
            'btnBorderWidth': random.choice([0, 2]),
            'btnBorderColor': random.choice(colors['borders']),
            'btnBorderRadius': random.randint(20, 32),
            'btnPaddingX': random.randint(24, 36),
            'btnPaddingY': random.randint(14, 20),
            'btnShadowX': 0,
            'btnShadowY': random.randint(4, 8),
            'btnShadowBlur': random.randint(20, 32),
            'btnShadowColor': 'rgba(0, 0, 0, 0.1)',
            'inputBg': '#FFFFFF',
            'inputTextColor': colors['dark_text'][0],
            'inputBorderWidth': random.randint(2, 3),
            'inputBorderColor': random.choice(colors['borders']),
            'inputBorderRadius': random.randint(16, 24),
            'inputPaddingX': random.randint(14, 20),
            'inputPaddingY': random.randint(10, 14),
        })
    elif style == 'cyberpunk':
        base_params.update({
            'btnBorderWidth': random.randint(2, 4),
            'btnBorderColor': primary_color,
            'btnBorderRadius': random.randint(4, 8),
            'btnPaddingX': random.randint(20, 32),
            'btnPaddingY': random.randint(12, 18),
            'btnShadowX': 0,
            'btnShadowY': 0,
            'btnShadowBlur': random.randint(12, 20),
            'btnShadowColor': f"{primary_color}CC",
            'inputBg': '#0A0A0A',
            'inputTextColor': body_text_color,
            'inputBorderWidth': random.randint(2, 3),
            'inputBorderColor': primary_color,
            'inputBorderRadius': random.randint(4, 8),
            'inputPaddingX': random.randint(14, 18),
            'inputPaddingY': random.randint(10, 14),
        })
    else:  # modern_minimal
        base_params.update({
            'btnBorderWidth': random.choice([0, 1, 2]),
            'btnBorderColor': random.choice(colors['borders']),
            'btnBorderRadius': random.randint(8, 16),
            'btnPaddingX': random.randint(20, 30),
            'btnPaddingY': random.randint(12, 18),
            'btnShadowX': 0,
            'btnShadowY': random.randint(3, 6),
            'btnShadowBlur': random.randint(8, 16),
            'btnShadowColor': 'rgba(0, 0, 0, 0.15)',
            'inputBg': '#FFFFFF' if bg_color not in ['#000000', '#1A1A1A', '#2D2D2D'] else '#1A1A1A',
            'inputTextColor': body_text_color,
            'inputBorderWidth': random.randint(1, 3),
            'inputBorderColor': random.choice(colors['borders']),
            'inputBorderRadius': random.randint(8, 14),
            'inputPaddingX': random.randint(14, 18),
            'inputPaddingY': random.randint(10, 14),
        })
    
    return base_params


def generate_realistic_ui_params():
    """Legacy function for backward compatibility."""
    return generate_diverse_ui_params()
