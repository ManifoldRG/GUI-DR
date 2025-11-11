"""
Type 1: Precision GUI Element Understanding - Viewport Zoom
"""
def generate_zoom_js() -> str:
    """Generate JavaScript for viewport zoom (Type 1)."""
    return """
            // Type 1: Precision GUI element understanding - Viewport zoom
            if (params.enableZoom) {
                const zoomLevel = params.zoomLevel || 0.7;
                document.body.style.transform = `scale(${zoomLevel})`;
                document.body.style.transformOrigin = 'top left';
                document.body.style.width = `${100 / zoomLevel}%`;
                document.body.style.height = `${100 / zoomLevel}%`;
            }
    """

