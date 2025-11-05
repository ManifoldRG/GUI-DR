import random
import re


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
    style = random.choice(['neobrutalism', 'glassmorphism', 'neumorphism', 'modern_minimal', 'retro_vibrant', 'dark_mode', 'pastel_dream', 'cyberpunk'])
    
    # Dramatically expanded color palettes with vibrant, saturated colors
    color_palettes = {
        'neobrutalism': {
            'backgrounds': ['#FFFF00', '#00FF00', '#FF00FF', '#00FFFF', '#FF6B35', '#FF1744', '#00E676', '#FF1744', '#E91E63', '#9C27B0', '#FF5722', '#FFC107', '#4CAF50', '#2196F3'],
            'primaries': ['#000000', '#FF0000', '#0000FF', '#1E40AF', '#991B1B', '#E91E63', '#9C27B0', '#FF5722', '#FFC107', '#4CAF50', '#2196F3', '#F44336'],
            'dark_text': ['#000000', '#1F2937', '#111827'],
            'light_text': ['#FFFFFF', '#F9FAFB'],
            'borders': ['#000000', '#1F2937', '#0F172A', '#FF0000', '#0000FF']
        },
        'glassmorphism': {
            'backgrounds': ['rgba(255, 255, 255, 0.1)', 'rgba(255, 255, 255, 0.15)', 'rgba(240, 248, 255, 0.12)'],
            'solid_backgrounds': ['#FFFFFF', '#F8FAFC', '#F1F5F9', '#E8F4F8', '#FFF5F5'],
            'primaries': ['#1D4ED8', '#7C3AED', '#DB2777', '#0D9488', '#D97706', '#2563EB', '#EC4899', '#14B8A6', '#F59E0B', '#8B5CF6', '#EF4444'],
            'dark_text': ['#0F172A', '#1E293B', '#111827'],
            'light_text': ['#FFFFFF', '#F8FAFC'],
            'borders': ['rgba(255, 255, 255, 0.3)', 'rgba(255, 255, 255, 0.4)', 'rgba(0, 0, 0, 0.1)']
        },
        'neumorphism': {
            'backgrounds': ['#E0E5EC', '#DDE1E7', '#E4EBF5', '#F0F0F3', '#EFEEEE', '#E8EDF2', '#E2E8F0', '#D6DBDF', '#EAEDED'],
            'primaries': ['#4F46E5', '#0891B2', '#7C3AED', '#DC2626', '#D97706', '#6366F1', '#10B981', '#F59E0B', '#EF4444'],
            'dark_text': ['#1E293B', '#334155', '#0F172A'],
            'light_text': ['#FFFFFF', '#F8FAFC'],
            'borders': ['#CBD5E1', '#94A3B8']
        },
        'modern_minimal': {
            'backgrounds': ['#FFFFFF', '#F9FAFB', '#F3F4F6', '#FAFAFA', '#F8F9FA', '#000000', '#1A1A1A', '#2D2D2D'],
            'primaries': ['#2563EB', '#7C3AED', '#DC2626', '#059669', '#D97706', '#0891B2', '#EF4444', '#8B5CF6', '#14B8A6', '#F59E0B'],
            'dark_text': ['#111827', '#1F2937', '#374151'],
            'light_text': ['#FFFFFF', '#F9FAFB'],
            'borders': ['#E5E7EB', '#D1D5DB', '#9CA3AF', '#000000']
        },
        'retro_vibrant': {
            'backgrounds': ['#FFE5EC', '#E0F2F7', '#FFF9C4', '#F3E5F5', '#FFE0B2', '#C8E6C9', '#FFCCBC', '#F0F4C3', '#FFCDD2', '#BBDEFB', '#FFF9C4', '#E1BEE7'],
            'primaries': ['#C2185B', '#1976D2', '#D84315', '#7B1FA2', '#0288D1', '#C62828', '#6A1B9A', '#E91E63', '#0097A7', '#FF5722', '#FFC107'],
            'dark_text': ['#1A1A1A', '#2C2C2C', '#212121'],
            'light_text': ['#FFFFFF', '#FAFAFA'],
            'borders': ['#C2185B', '#1976D2', '#7B1FA2', '#FF5722']
        },
        'dark_mode': {
            'backgrounds': ['#000000', '#1A1A1A', '#1E1E1E', '#2D2D2D', '#121212', '#0A0A0A'],
            'primaries': ['#00FF00', '#00FFFF', '#FF00FF', '#FFFF00', '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7'],
            'dark_text': ['#FFFFFF', '#F0F0F0', '#E0E0E0'],
            'light_text': ['#FFFFFF', '#F9FAFB'],
            'borders': ['#333333', '#444444', '#00FF00', '#00FFFF']
        },
        'pastel_dream': {
            'backgrounds': ['#FFE5F1', '#E5F3FF', '#FFF5E5', '#F0E5FF', '#E5FFE5', '#FFE5E5', '#E5FFFF', '#FFF0E5'],
            'primaries': ['#FF6B9D', '#6B9DFF', '#FFB84D', '#9D6BFF', '#6BFF9D', '#FF6B6B', '#6B6BFF', '#FF9D6B'],
            'dark_text': ['#2C2C2C', '#3A3A3A', '#1A1A1A'],
            'light_text': ['#FFFFFF', '#FAFAFA'],
            'borders': ['#FFB3D1', '#B3D1FF', '#FFD9B3', '#D9B3FF']
        },
        'cyberpunk': {
            'backgrounds': ['#0A0A0A', '#1A0033', '#000033', '#330000', '#003300', '#1A1A2E'],
            'primaries': ['#00FFFF', '#FF00FF', '#FFFF00', '#00FF00', '#FF0080', '#80FF00', '#FF8000', '#0080FF'],
            'dark_text': ['#00FFFF', '#FF00FF', '#FFFFFF', '#FFFF00'],
            'light_text': ['#FFFFFF', '#00FFFF', '#FF00FF'],
            'borders': ['#00FFFF', '#FF00FF', '#FFFF00', '#00FF00']
        }
    }
    
    colors = color_palettes[style]
    bg_color = random.choice(colors['backgrounds'])
    primary_color = random.choice(colors['primaries'])
    body_text_color = find_accessible_text_color(bg_color, colors['dark_text'], colors['light_text'])
    btn_text_color = find_accessible_text_color(primary_color, colors['dark_text'], colors['light_text'])
    
    # Dramatically diverse font combinations - mixing serif/sans-serif, decorative fonts, monospace
    fonts = {
        'neobrutalism': [
            ("'Space Grotesk', sans-serif", "'Inter', sans-serif"),
            ("'Bebas Neue', sans-serif", "'Roboto', sans-serif"),
            ("'Archivo Black', sans-serif", "'Work Sans', sans-serif"),
            ("'Oswald', sans-serif", "'Montserrat', sans-serif"),
            ("'Impact', sans-serif", "'Arial Black', sans-serif"),
            ("'Anton', sans-serif", "'Open Sans', sans-serif"),
            ("'Black Ops One', sans-serif", "'Roboto Condensed', sans-serif"),
        ],
        'glassmorphism': [
            ("'Poppins', sans-serif", "'Inter', sans-serif"),
            ("'Sora', sans-serif", "'Heebo', sans-serif"),
            ("'Epilogue', sans-serif", "'Mulish', sans-serif"),
            ("'Manrope', sans-serif", "'DM Sans', sans-serif"),
            ("'Plus Jakarta Sans', sans-serif", "'Inter', sans-serif"),
            ("'Outfit', sans-serif", "'DM Sans', sans-serif"),
        ],
        'neumorphism': [
            ("'Nunito', sans-serif", "'Open Sans', sans-serif"),
            ("'Quicksand', sans-serif", "'Lato', sans-serif"),
            ("'Comfortaa', sans-serif", "'Rubik', sans-serif"),
            ("'Cabin', sans-serif", "'Source Sans Pro', sans-serif"),
            ("'Karla', sans-serif", "'PT Sans', sans-serif"),
        ],
        'modern_minimal': [
            ("'Playfair Display', serif", "'Source Sans Pro', sans-serif"),
            ("'Merriweather', serif", "'Open Sans', sans-serif"),
            ("'Lora', serif", "'Roboto', sans-serif"),
            ("'Roboto', sans-serif", "'Roboto Slab', serif"),
            ("'Montserrat', sans-serif", "'Lato', sans-serif"),
            ("'Georgia', serif", "'Verdana', sans-serif"),
            ("'Crimson Text', serif", "'Work Sans', sans-serif"),
            ("'Libre Baskerville', serif", "'Raleway', sans-serif"),
            ("'PT Serif', serif", "'PT Sans', sans-serif"),
            ("'Cormorant Garamond', serif", "'Proxima Nova', sans-serif"),
        ],
        'retro_vibrant': [
            ("'Fredoka One', sans-serif", "'Raleway', sans-serif"),
            ("'Righteous', sans-serif", "'Poppins', sans-serif"),
            ("'Audiowide', sans-serif", "'Exo 2', sans-serif"),
            ("'Bangers', sans-serif", "'Oswald', sans-serif"),
            ("'Luckiest Guy', sans-serif", "'Nunito', sans-serif"),
            ("'Bungee', sans-serif", "'Montserrat', sans-serif"),
        ],
        'dark_mode': [
            ("'Orbitron', sans-serif", "'Rajdhani', sans-serif"),
            ("'Exo 2', sans-serif", "'Titillium Web', sans-serif"),
            ("'Russo One', sans-serif", "'Roboto Mono', monospace"),
            ("'Aldrich', sans-serif", "'Courier New', monospace"),
            ("'Share Tech Mono', monospace", "'Roboto', sans-serif"),
        ],
        'pastel_dream': [
            ("'Comfortaa', sans-serif", "'Quicksand', sans-serif"),
            ("'Nunito', sans-serif", "'Poppins', sans-serif"),
            ("'Cabin', sans-serif", "'Open Sans', sans-serif"),
            ("'Kalam', sans-serif", "'Lato', sans-serif"),
            ("'Indie Flower', cursive", "'Roboto', sans-serif"),
        ],
        'cyberpunk': [
            ("'Orbitron', sans-serif", "'Rajdhani', sans-serif"),
            ("'Exo 2', sans-serif", "'Roboto Mono', monospace"),
            ("'Russo One', sans-serif", "'Courier New', monospace"),
            ("'Share Tech Mono', monospace", "'Consolas', monospace"),
            ("'Fira Code', monospace", "'Fira Mono', monospace"),
        ]
    }
    heading_font, body_font = random.choice(fonts.get(style, fonts['modern_minimal']))
    
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
