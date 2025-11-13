"""
Type 2: Dense Information - CSS-based compression to increase information density.
Compresses spacing, fonts, and elements while maintaining readability.
"""


def generate_dense_info_js() -> str:
    """Generate JavaScript for dense information modifications (Type 2).
    
    Uses element-wise and text-wise compression to increase density:
    - Reduces font sizes with safe minimums
    - Fixes text overflow issues
    - Allows elements to expand to fit content when needed
    
    Returns:
        JavaScript code string
    """
    return """
            // Type 2: Dense information (CSS compression)
            if (params.enableDenseInfo) {
                applyDensityCompression();
            }
    """ + _generate_compression_js()


def _generate_compression_js() -> str:
    """Generate JavaScript for CSS-based density compression."""
    return """
            function applyDensityCompression() {
                // Safe minimum thresholds to prevent unreadability
                const MIN_FONT_SIZE = 11;  // Minimum readable font size (px)
                
                // Compression ratios - only for font sizes
                const FONT_RATIO = 0.8;  // Reduce font size by 20%
                
                // Helper: Apply safe reduction with minimum threshold
                function safeReduce(value, ratio, minValue) {
                    const reduced = Math.max(value * ratio, minValue);
                    return Math.round(reduced);
                }
                
                // 1. Prevent text cutoff - apply overflow protection to text elements
                // Only target elements that commonly have text overflow issues, not layout divs
                const textElements = document.querySelectorAll('button, a, p, span, li, label, .text, .content');
                textElements.forEach(el => {
                    const style = window.getComputedStyle(el);
                    // Only apply if element has text overflow issues AND is not a layout container
                    const isLayoutContainer = el.tagName === 'DIV' && (
                        el.classList.contains('container') || 
                        el.classList.contains('wrapper') || 
                        el.classList.contains('layout') ||
                        el.id.includes('container') ||
                        el.id.includes('wrapper')
                    );
                    
                    if (!isLayoutContainer && (style.overflow === 'hidden' || style.textOverflow === 'ellipsis' || style.whiteSpace === 'nowrap')) {
                        // Only fix overflow for elements that actually have overflow issues
                        el.style.textOverflow = 'clip';
                        el.style.whiteSpace = 'normal';
                        el.style.wordWrap = 'break-word';
                        el.style.overflowWrap = 'break-word';
                        // Only set overflow: visible if it was hidden (don't change other overflow values)
                        if (style.overflow === 'hidden') {
                            el.style.overflow = 'visible';
                        }
                    }
                });
                
                // 2. Allow buttons/links to expand if they have fixed widths that are too small
                const interactiveElements = document.querySelectorAll('button, a, input[type="button"], input[type="submit"]');
                interactiveElements.forEach(el => {
                    const style = window.getComputedStyle(el);
                    
                    // Ensure text doesn't get cut off in buttons/links
                    if (style.textOverflow === 'ellipsis' || style.whiteSpace === 'nowrap') {
                        el.style.textOverflow = 'clip';
                        el.style.whiteSpace = 'normal';
                        el.style.wordWrap = 'break-word';
                        el.style.overflowWrap = 'break-word';
                        // Only set overflow: visible if it was explicitly hidden
                        if (style.overflow === 'hidden') {
                            el.style.overflow = 'visible';
                        }
                    }
                    
                    // Allow buttons to expand if they have fixed widths that are too small
                    // But be conservative - only remove very small widths to prevent breaking layout
                    if (style.width && style.width !== 'auto' && !style.width.includes('%')) {
                        const widthMatch = style.width.match(/^(\d+)px$/);
                        if (widthMatch && parseFloat(widthMatch[1]) < 150) {
                            // Only remove very small fixed widths
                            el.style.width = 'auto';
                        }
                    }
                    if (style.maxWidth && style.maxWidth !== 'none' && !style.maxWidth.includes('%')) {
                        const maxWidthMatch = style.maxWidth.match(/^(\d+)px$/);
                        if (maxWidthMatch && parseFloat(maxWidthMatch[1]) < 200) {
                            // Only remove very small max-widths
                            el.style.maxWidth = 'none';
                        }
                    }
                });
                
                // 3. Compress font sizes (body text, paragraphs, spans)
                // Exclude layout divs - only target actual text elements
                const textElementsForFont = document.querySelectorAll('p, span, li, a, button, label, .text, .content');
                textElementsForFont.forEach(el => {
                    const style = window.getComputedStyle(el);
                    const fontSize = parseFloat(style.fontSize);
                    
                    // Only set text wrapping properties, don't force overflow: visible
                    // This prevents text from breaking out of containers
                    if (style.whiteSpace === 'nowrap') {
                        el.style.whiteSpace = 'normal';
                    }
                    if (style.textOverflow === 'ellipsis') {
                        el.style.textOverflow = 'clip';
                    }
                    el.style.wordWrap = 'break-word';
                    el.style.overflowWrap = 'break-word';
                    
                    // Reduce font size only, keeping minimum for readability
                    if (fontSize && fontSize > MIN_FONT_SIZE) {
                        const reduced = safeReduce(fontSize, FONT_RATIO, MIN_FONT_SIZE);
                        el.style.fontSize = reduced + 'px';
                    }
                });
            }
    """


