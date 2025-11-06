"""
UI Style Data - Color palettes and font combinations for different design styles.
Extracted from randomization.py for better maintainability.
"""

# Color palettes for 8 different design styles
COLOR_PALETTES = {
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

# Font combinations for each style
FONT_COMBINATIONS = {
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

