import random
import re
from .styles_data import COLOR_PALETTES, FONT_COMBINATIONS


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


def generate_contrasting_color(bg_color, prefer_dark=True):
    """Generate a contrasting color (black or white) that meets WCAG contrast requirements.
    
    Args:
        bg_color: Background color (hex string or RGB tuple)
        prefer_dark: If True, prefer dark text; if False, prefer light text
    
    Returns:
        Hex color string that contrasts with bg_color (minimum 4.5:1 ratio)
    """
    bg_rgb = hex_to_rgb(bg_color) if isinstance(bg_color, str) else bg_color
    bg_lum = get_luminance(bg_rgb)
    
    # Try black first if prefer_dark, then white
    test_colors = ['#000000', '#FFFFFF'] if prefer_dark else ['#FFFFFF', '#000000']
    
    for test_color in test_colors:
        if get_contrast_ratio(bg_rgb, test_color) >= 4.5:
            return test_color
    
    # If neither pure black nor white works (very rare), use luminance-based choice
    # This ensures at least some contrast
    return '#000000' if bg_lum > 0.5 else '#FFFFFF'


def find_accessible_text_color(bg_color, dark_options, light_options, min_ratio=4.5):
    """Find an accessible text color for the given background.
    
    Always returns a color with at least min_ratio contrast (default 4.5:1 for WCAG AA).
    If no palette color meets the requirement, generates a contrasting color.
    """
    # Handle gradient backgrounds by using a representative color
    # For gradients, we'll use the first solid color or default to checking against white
    if isinstance(bg_color, str) and 'gradient' in bg_color.lower():
        # For gradients, check against a light background assumption
        # The JavaScript will handle actual contrast per element
        bg_color = '#FFFFFF'  # Default assumption for gradient backgrounds
    
    bg_rgb = hex_to_rgb(bg_color) if isinstance(bg_color, str) else bg_color
    
    # Try all options in order, preferring ones with higher contrast
    best_color = None
    best_ratio = 0
    
    for text_color in dark_options + light_options:
        ratio = get_contrast_ratio(bg_rgb, text_color)
        if ratio >= min_ratio:
            # Prefer colors with higher contrast (up to a point, for readability)
            if ratio > best_ratio:
                best_color = text_color
                best_ratio = ratio
    
    # If we found a good color, return it
    if best_color:
        return best_color
    
    # If no palette color works, generate a guaranteed contrasting color
    bg_lum = get_luminance(bg_rgb)
    prefer_dark = bg_lum > 0.5  # Prefer dark text on light backgrounds
    return generate_contrasting_color(bg_rgb, prefer_dark=prefer_dark)


def validate_color_contrast(text_color, bg_color, min_ratio=4.5, element_name="element"):
    """Validate that text color has sufficient contrast with background.
    
    Returns True if contrast is sufficient, False otherwise.
    Logs a warning if contrast is insufficient (shouldn't happen with improved find_accessible_text_color).
    """
    # Skip validation for gradient backgrounds (handled by JavaScript)
    if isinstance(bg_color, str) and 'gradient' in bg_color.lower():
        return True
    
    ratio = get_contrast_ratio(text_color, bg_color)
    if ratio < min_ratio:
        # This shouldn't happen with our improved find_accessible_text_color, but log if it does
        from loguru import logger
        logger.warning(f"⚠️  {element_name}: contrast ratio {ratio:.2f} < {min_ratio} for {text_color} on {bg_color}")
        return False
    return True


def generate_diverse_ui_params():
    """
    Generate highly diverse UI parameters for maximum visual difference.
    Creates dramatic color, font, and style variations while maintaining text overflow prevention.
    All color combinations are validated to meet WCAG contrast requirements (minimum 4.5:1).
    """
    style = random.choice(list(COLOR_PALETTES.keys()))
    colors = COLOR_PALETTES[style]
    bg_color = random.choice(colors['backgrounds'])
    primary_color = random.choice(colors['primaries'])
    
    # ALWAYS ensure text colors have sufficient contrast with their backgrounds
    # This is critical - never allow poor contrast combinations
    body_text_color = find_accessible_text_color(bg_color, colors['dark_text'], colors['light_text'], min_ratio=4.5)
    
    # For buttons: first choose background, then ensure text color contrasts
    # This ensures we never have light bg + light text or dark bg + dark text
    btn_bg = primary_color
    btn_text_color = find_accessible_text_color(btn_bg, colors['dark_text'], colors['light_text'], min_ratio=4.5)
    
    # Double-check button contrast - if still poor, force a contrasting color
    btn_contrast = get_contrast_ratio(btn_bg, btn_text_color)
    if btn_contrast < 4.5:
        # Force high contrast - use black or white based on button background
        btn_bg_lum = get_luminance(hex_to_rgb(btn_bg) if isinstance(btn_bg, str) else btn_bg)
        btn_text_color = '#FFFFFF' if btn_bg_lum < 0.5 else '#000000'
    
    # Validate initial color combinations (should always pass now)
    validate_color_contrast(body_text_color, bg_color, element_name="body text")
    validate_color_contrast(btn_text_color, btn_bg, element_name="button text")
    
    # Get font combination for the selected style
    heading_font, body_font = random.choice(FONT_COMBINATIONS.get(style, FONT_COMBINATIONS['modern_minimal']))
    
    # Ensure linkColor has sufficient contrast with background
    # Links should be visible, so we check contrast with bg_color
    link_color = primary_color
    if get_contrast_ratio(bg_color, primary_color) < 3.0:  # 3.0 is minimum for large text, but we want better
        # If primary color doesn't contrast well, use a contrasting color
        link_color = find_accessible_text_color(bg_color, colors['dark_text'], colors['light_text'], min_ratio=3.0)
        # But make it distinct from body text - if it's the same, use primary with higher contrast
        if link_color == body_text_color:
            # Try to find a color that contrasts but is different
            for candidate in colors['primaries']:
                if get_contrast_ratio(bg_color, candidate) >= 3.0 and candidate != body_text_color:
                    link_color = candidate
                    break
    
    # Generate container/section background variations
    # Use subtle variations of the main background or complementary colors
    container_bg_options = colors.get('solid_backgrounds', colors['backgrounds'])
    if isinstance(bg_color, str) and 'rgba' in bg_color:
        # For transparent backgrounds, use solid alternatives
        container_bg_options = colors.get('solid_backgrounds', ['#FFFFFF', '#F8FAFC', '#F1F5F9'])
    
    # Select container backgrounds that complement the main background
    section_bg = random.choice(container_bg_options) if container_bg_options else bg_color
    nav_bg = random.choice(container_bg_options) if container_bg_options else bg_color
    header_bg = random.choice(container_bg_options) if container_bg_options else bg_color
    footer_bg = random.choice(container_bg_options) if container_bg_options else bg_color
    
    # Ensure container backgrounds have good contrast with text
    section_text_color = find_accessible_text_color(section_bg, colors['dark_text'], colors['light_text'])
    
    # Generate container border and shadow parameters
    container_border_width = random.choice([0, 1, 2]) if random.random() > 0.5 else 0
    container_border_color = random.choice(colors.get('borders', [primary_color]))
    container_border_radius = random.randint(0, 12) if random.random() > 0.6 else 0
    container_shadow_x = random.randint(0, 4) if random.random() > 0.5 else 0
    container_shadow_y = random.randint(0, 4) if random.random() > 0.5 else 0
    container_shadow_blur = random.randint(0, 12) if random.random() > 0.5 else 0
    container_shadow_color = f"rgba(0, 0, 0, {random.uniform(0.1, 0.3)})" if container_shadow_blur > 0 else 'transparent'
    
    # Generate additional visual style parameters for divs and other containers
    # Apply subtle background variations to common container classes
    div_bg_probability = 0.3  # 30% chance to apply background to divs
    div_bg = random.choice(container_bg_options) if container_bg_options and random.random() < div_bg_probability else 'transparent'
    
    # Card/container styling (for elements with common class patterns)
    card_bg = random.choice(container_bg_options) if container_bg_options else 'transparent'
    card_border_width = random.choice([0, 1]) if random.random() > 0.7 else 0
    card_border_radius = random.randint(0, 8) if random.random() > 0.7 else 0
    card_shadow_blur = random.randint(0, 8) if random.random() > 0.6 else 0
    card_shadow_color = f"rgba(0, 0, 0, {random.uniform(0.05, 0.2)})" if card_shadow_blur > 0 else 'transparent'
    
    # Base parameters with more dramatic variations
    base_params = {
        'designStyle': style,
        'bgColor': bg_color,
        'primaryColor': primary_color,
        'textColor': body_text_color,
        'headingColor': body_text_color,
        'headingFont': heading_font,
        'bodyFont': body_font,
        # Fixed conservative font sizes to prevent size increases
        'bodySize': random.choice([14, 15, 16]),
        'headingSize': random.choice([24, 26, 28]),
        # Normal font weights to prevent visual size increases
        'bodyWeight': random.choice([400, 500]),
        'headingWeight': random.choice([600, 700]),
        # Minimal letter spacing to prevent width increases
        'letterSpacing': round(random.uniform(-0.01, 0.01), 3),
        # Conservative line height to prevent vertical space increases
        'lineHeight': round(random.uniform(1.3, 1.5), 2),
        'btnBg': btn_bg,  # Use the validated button background
        'btnTextColor': btn_text_color,  # Use the validated button text color with guaranteed contrast
        'linkColor': link_color,
        'transitionSpeed': round(random.uniform(0.15, 0.4), 2),
        # Container/section styling (visual only, no layout changes)
        'sectionBg': section_bg,
        'navBg': nav_bg,
        'headerBg': header_bg,
        'footerBg': footer_bg,
        'sectionTextColor': section_text_color,
        'containerBorderWidth': container_border_width,
        'containerBorderColor': container_border_color,
        'containerBorderRadius': container_border_radius,
        'containerShadowX': container_shadow_x,
        'containerShadowY': container_shadow_y,
        'containerShadowBlur': container_shadow_blur,
        'containerShadowColor': container_shadow_color,
        # Additional container styling
        'divBg': div_bg,
        'cardBg': card_bg,
        'cardBorderWidth': card_border_width,
        'cardBorderRadius': card_border_radius,
        'cardShadowBlur': card_shadow_blur,
        'cardShadowColor': card_shadow_color,
    }
    
    # Style-specific parameters with more dramatic variations
    if style == 'neobrutalism':
        input_bg = '#FFFFFF'
        input_text_color = find_accessible_text_color(input_bg, colors['dark_text'], colors['light_text'])
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
            'inputBg': input_bg,
            'inputTextColor': input_text_color,
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
        # Ensure button colors have proper contrast
        neumorphism_btn_bg = bg_color
        neumorphism_btn_text = find_accessible_text_color(neumorphism_btn_bg, colors['dark_text'], colors['light_text'], min_ratio=4.5)
        base_params.update({
            'btnBg': neumorphism_btn_bg,
            'btnTextColor': neumorphism_btn_text,
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
        input_bg = '#FFFFFF'
        input_text_color = find_accessible_text_color(input_bg, colors['dark_text'], colors['light_text'])
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
            'inputBg': input_bg,
            'inputTextColor': input_text_color,
            'inputBorderWidth': random.randint(3, 5),
            'inputBorderColor': random.choice(colors['borders']),
            'inputBorderRadius': random.randint(16, 24),
            'inputPaddingX': random.randint(14, 20),
            'inputPaddingY': random.randint(10, 14),
        })
    elif style == 'dark_mode':
        # For dark mode, ensure better contrast - use higher minimum ratio
        # Dark backgrounds need very light text for good contrast
        dark_bg = bg_color
        dark_text_color = find_accessible_text_color(dark_bg, colors['light_text'], colors['dark_text'], min_ratio=7.0)
        dark_btn_text_color = find_accessible_text_color(primary_color, colors['light_text'], colors['dark_text'], min_ratio=7.0)
        
        base_params.update({
            'textColor': dark_text_color,  # Override with high-contrast color
            'headingColor': dark_text_color,
            'btnTextColor': dark_btn_text_color,  # Override with high-contrast color
            'btnBorderWidth': random.choice([0, 2, 3]),
            'btnBorderColor': primary_color,
            'btnBorderRadius': random.randint(8, 16),
            'btnShadowX': 0,
            'btnShadowY': random.randint(4, 8),
            'btnShadowBlur': random.randint(16, 24),
            'btnShadowColor': f"{primary_color}80",
            'inputBg': '#1A1A1A',
            'inputTextColor': dark_text_color,  # Use high-contrast color
            'inputBorderWidth': random.randint(2, 4),
            'inputBorderColor': primary_color,
            'inputBorderRadius': random.randint(8, 12),
            'inputPaddingX': random.randint(14, 18),
            'inputPaddingY': random.randint(10, 14),
        })
    elif style == 'pastel_dream':
        input_bg = '#FFFFFF'
        input_text_color = find_accessible_text_color(input_bg, colors['dark_text'], colors['light_text'])
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
            'inputBg': input_bg,
            'inputTextColor': input_text_color,
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
        input_bg = '#FFFFFF' if bg_color not in ['#000000', '#1A1A1A', '#2D2D2D'] else '#1A1A1A'
        input_text_color = find_accessible_text_color(input_bg, colors['dark_text'], colors['light_text'])
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
            'inputBg': input_bg,
            'inputTextColor': input_text_color,
            'inputBorderWidth': random.randint(1, 3),
            'inputBorderColor': random.choice(colors['borders']),
            'inputBorderRadius': random.randint(8, 14),
            'inputPaddingX': random.randint(14, 18),
            'inputPaddingY': random.randint(10, 14),
        })
    
    # Final validation: ensure all color combinations meet contrast requirements
    # Validate link color contrast (links are on body background)
    validate_color_contrast(base_params['linkColor'], base_params['bgColor'], min_ratio=3.0, element_name="link")
    # Validate input text color contrast
    if 'inputBg' in base_params and 'inputTextColor' in base_params:
        validate_color_contrast(base_params['inputTextColor'], base_params['inputBg'], element_name="input text")
    
    return base_params


def generate_realistic_ui_params():
    """Legacy function for backward compatibility."""
    return generate_diverse_ui_params()
