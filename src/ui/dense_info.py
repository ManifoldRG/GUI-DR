"""
Type 2: Dense Information - CSS-based compression to increase information density.
Compresses spacing, fonts, and elements while maintaining readability.
"""


def generate_dense_info_js() -> str:
    """Generate JavaScript for dense information modifications (Type 2).
    
    Uses CSS compression to increase density:
    - Reduces spacing (gaps, padding, margins) with safe minimums
    - Reduces font sizes slightly with safe minimums
    - Reduces line heights slightly with safe minimums
    
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
                // Safe minimum thresholds to prevent overlap and unreadability
                const MIN_FONT_SIZE = 11;  // Minimum readable font size (px) - slightly lower for more compression
                const MIN_LINE_HEIGHT = 1.15;  // Minimum readable line height (multiplier) - tighter
                const MIN_GAP = 3;  // Minimum gap between elements (px) - tighter
                const MIN_PADDING = 6;  // Minimum padding in containers (px) - tighter
                const MIN_MARGIN = 4;  // Minimum margin between sections (px) - tighter
                
                // Compression ratios (more aggressive compression)
                const FONT_RATIO = 0.8;  // Reduce font size by 20% (was 15%)
                const LINE_HEIGHT_RATIO = 0.85;  // Reduce line height by 15% (was 10%)
                const SPACING_RATIO = 0.5;  // Reduce spacing by 50% (was 40%)
                
                // Helper: Apply safe reduction with minimum threshold
                function safeReduce(value, ratio, minValue) {
                    const reduced = Math.max(value * ratio, minValue);
                    return Math.round(reduced);
                }
                
                // Helper: Parse and reduce CSS value
                function reduceSpacing(cssValue, ratio, minValue) {
                    if (!cssValue || cssValue === '0' || cssValue === '0px') {
                        return minValue + 'px';
                    }
                    const match = cssValue.match(/(\d+(?:\.\d+)?)(px|em|rem)?/);
                    if (match) {
                        const num = parseFloat(match[1]);
                        const unit = match[2] || 'px';
                        const reduced = safeReduce(num, ratio, minValue);
                        return reduced + unit;
                    }
                    return cssValue;
                }
                
                // 0. Prevent text cutoff - apply overflow protection to text-containing elements
                const textContainers = document.querySelectorAll('button, a, p, span, div, li, label, .text, .content, .menu, .list, nav, ul, ol');
                textContainers.forEach(el => {
                    const style = window.getComputedStyle(el);
                    // Only apply if element has text overflow issues
                    if (style.overflow === 'hidden' || style.textOverflow === 'ellipsis' || style.whiteSpace === 'nowrap') {
                        el.style.overflow = 'visible';
                        el.style.textOverflow = 'clip';
                        el.style.whiteSpace = 'normal';
                        el.style.wordWrap = 'break-word';
                        el.style.overflowWrap = 'break-word';
                    }
                    // Allow containers to expand to fit content (remove fixed widths)
                    if (style.maxWidth && style.maxWidth !== 'none' && !style.maxWidth.includes('%')) {
                        const maxWidthMatch = style.maxWidth.match(/^(\d+)px$/);
                        if (maxWidthMatch && parseFloat(maxWidthMatch[1]) < 2000) {
                            // Only remove small fixed max-widths
                            el.style.maxWidth = 'none';
                        }
                    }
                    if (style.width && style.width !== 'auto' && !style.width.includes('%')) {
                        const widthMatch = style.width.match(/^(\d+)px$/);
                        if (widthMatch && parseFloat(widthMatch[1]) < 1000) {
                            // Only remove small fixed widths, keep large ones
                            el.style.width = 'auto';
                            el.style.minWidth = 'fit-content';
                        }
                    }
                });
                
                // 1. Compress container spacing (nav, ul, ol, menus, lists)
                const containers = document.querySelectorAll('nav, ul, ol, .menu, .list, .navbar, header, footer, section, article, aside');
                containers.forEach(container => {
                    const style = window.getComputedStyle(container);
                    
                    // Ensure container can expand
                    container.style.overflow = 'visible';
                    container.style.minWidth = 'fit-content';
                    
                    // Reduce gap (for flex/grid containers)
                    if (style.gap && style.gap !== 'normal' && style.gap !== '0px') {
                        container.style.gap = reduceSpacing(style.gap, SPACING_RATIO, MIN_GAP);
                    }
                    
                    // Reduce padding
                    if (style.paddingTop) {
                        container.style.paddingTop = reduceSpacing(style.paddingTop, SPACING_RATIO, MIN_PADDING);
                    }
                    if (style.paddingBottom) {
                        container.style.paddingBottom = reduceSpacing(style.paddingBottom, SPACING_RATIO, MIN_PADDING);
                    }
                    if (style.paddingLeft) {
                        container.style.paddingLeft = reduceSpacing(style.paddingLeft, SPACING_RATIO, MIN_PADDING);
                    }
                    if (style.paddingRight) {
                        container.style.paddingRight = reduceSpacing(style.paddingRight, SPACING_RATIO, MIN_PADDING);
                    }
                });
                
                // 2. Compress list item spacing
                const listItems = document.querySelectorAll('li, .list-item, .menu-item, .nav-item');
                listItems.forEach(item => {
                    const style = window.getComputedStyle(item);
                    
                    // Reduce margin
                    if (style.marginTop) {
                        item.style.marginTop = reduceSpacing(style.marginTop, SPACING_RATIO, MIN_MARGIN);
                    }
                    if (style.marginBottom) {
                        item.style.marginBottom = reduceSpacing(style.marginBottom, SPACING_RATIO, MIN_MARGIN);
                    }
                    
                    // Reduce padding
                    if (style.paddingTop) {
                        item.style.paddingTop = reduceSpacing(style.paddingTop, SPACING_RATIO, MIN_PADDING);
                    }
                    if (style.paddingBottom) {
                        item.style.paddingBottom = reduceSpacing(style.paddingBottom, SPACING_RATIO, MIN_PADDING);
                    }
                });
                
                // 3. Compress button/link spacing
                const interactiveElements = document.querySelectorAll('button, a, input[type="button"], input[type="submit"]');
                interactiveElements.forEach(el => {
                    const style = window.getComputedStyle(el);
                    
                    // Ensure text doesn't get cut off in buttons/links (but preserve layout)
                    if (style.overflow === 'hidden' || style.textOverflow === 'ellipsis' || style.whiteSpace === 'nowrap') {
                        el.style.overflow = 'visible';
                        el.style.textOverflow = 'clip';
                        el.style.whiteSpace = 'normal';
                        el.style.wordWrap = 'break-word';
                        el.style.overflowWrap = 'break-word';
                    }
                    // Allow buttons to expand if they have fixed widths that are too small
                    if (style.width && style.width !== 'auto' && !style.width.includes('%')) {
                        const widthMatch = style.width.match(/^(\d+)px$/);
                        if (widthMatch && parseFloat(widthMatch[1]) < 200) {
                            // Remove small fixed widths to allow text to fit
                            el.style.width = 'auto';
                            el.style.minWidth = 'fit-content';
                        }
                    }
                    if (style.maxWidth && style.maxWidth !== 'none' && !style.maxWidth.includes('%')) {
                        const maxWidthMatch = style.maxWidth.match(/^(\d+)px$/);
                        if (maxWidthMatch && parseFloat(maxWidthMatch[1]) < 300) {
                            el.style.maxWidth = 'none';
                        }
                    }
                    
                    // Reduce margin (external spacing)
                    if (style.marginLeft) {
                        el.style.marginLeft = reduceSpacing(style.marginLeft, SPACING_RATIO, MIN_MARGIN);
                    }
                    if (style.marginRight) {
                        el.style.marginRight = reduceSpacing(style.marginRight, SPACING_RATIO, MIN_MARGIN);
                    }
                    if (style.marginTop) {
                        el.style.marginTop = reduceSpacing(style.marginTop, SPACING_RATIO, MIN_MARGIN);
                    }
                    if (style.marginBottom) {
                        el.style.marginBottom = reduceSpacing(style.marginBottom, SPACING_RATIO, MIN_MARGIN);
                    }
                    
                    // Reduce padding (but keep minimum for usability)
                    const minButtonPadding = 4;  // Buttons need slightly less padding (reduced from 6)
                    if (style.paddingLeft) {
                        el.style.paddingLeft = reduceSpacing(style.paddingLeft, SPACING_RATIO, minButtonPadding);
                    }
                    if (style.paddingRight) {
                        el.style.paddingRight = reduceSpacing(style.paddingRight, SPACING_RATIO, minButtonPadding);
                    }
                    if (style.paddingTop) {
                        el.style.paddingTop = reduceSpacing(style.paddingTop, SPACING_RATIO, minButtonPadding);
                    }
                    if (style.paddingBottom) {
                        el.style.paddingBottom = reduceSpacing(style.paddingBottom, SPACING_RATIO, minButtonPadding);
                    }
                });
                
                // 4. Compress font sizes (body text, paragraphs, spans)
                const textElements = document.querySelectorAll('p, span, div, li, a, button, label, .text, .content');
                textElements.forEach(el => {
                    const style = window.getComputedStyle(el);
                    const fontSize = parseFloat(style.fontSize);
                    
                    // Ensure text wrapping and visibility
                    el.style.overflow = 'visible';
                    el.style.textOverflow = 'clip';
                    el.style.whiteSpace = 'normal';
                    el.style.wordWrap = 'break-word';
                    el.style.overflowWrap = 'break-word';
                    
                    if (fontSize && fontSize > MIN_FONT_SIZE) {
                        const reduced = safeReduce(fontSize, FONT_RATIO, MIN_FONT_SIZE);
                        el.style.fontSize = reduced + 'px';
                    }
                });
                
                // 5. Compress line heights
                textElements.forEach(el => {
                    const style = window.getComputedStyle(el);
                    const lineHeight = style.lineHeight;
                    
                    // Handle line-height as number (multiplier) or pixel value
                    if (lineHeight && lineHeight !== 'normal') {
                        const match = lineHeight.match(/(\d+(?:\.\d+)?)/);
                        if (match) {
                            const num = parseFloat(match[1]);
                            // If less than 5, treat as multiplier; otherwise as pixels
                            if (num < 5) {
                                const reduced = Math.max(num * LINE_HEIGHT_RATIO, MIN_LINE_HEIGHT);
                                el.style.lineHeight = reduced.toFixed(2);
                            } else {
                                const fontSize = parseFloat(window.getComputedStyle(el).fontSize) || MIN_FONT_SIZE;
                                const minLineHeightPx = fontSize * MIN_LINE_HEIGHT;
                                const reduced = safeReduce(num, LINE_HEIGHT_RATIO, minLineHeightPx);
                                el.style.lineHeight = reduced + 'px';
                            }
                        }
                    }
                });
                
                // 6. Compress paragraph spacing
                const paragraphs = document.querySelectorAll('p');
                paragraphs.forEach(p => {
                    const style = window.getComputedStyle(p);
                    
                    if (style.marginTop) {
                        p.style.marginTop = reduceSpacing(style.marginTop, SPACING_RATIO, MIN_MARGIN);
                    }
                    if (style.marginBottom) {
                        p.style.marginBottom = reduceSpacing(style.marginBottom, SPACING_RATIO, MIN_MARGIN);
                    }
                });
                
                // 7. Compress input field spacing
                const inputs = document.querySelectorAll('input, textarea, select');
                inputs.forEach(input => {
                    const style = window.getComputedStyle(input);
                    
                    // Reduce padding (but keep minimum for usability)
                    const minInputPadding = 4;  // Reduced from 6 for more compression
                    if (style.paddingLeft) {
                        input.style.paddingLeft = reduceSpacing(style.paddingLeft, SPACING_RATIO, minInputPadding);
                    }
                    if (style.paddingRight) {
                        input.style.paddingRight = reduceSpacing(style.paddingRight, SPACING_RATIO, minInputPadding);
                    }
                    if (style.paddingTop) {
                        input.style.paddingTop = reduceSpacing(style.paddingTop, SPACING_RATIO, minInputPadding);
                    }
                    if (style.paddingBottom) {
                        input.style.paddingBottom = reduceSpacing(style.paddingBottom, SPACING_RATIO, minInputPadding);
                    }
                    
                    // Reduce margin
                    if (style.marginTop) {
                        input.style.marginTop = reduceSpacing(style.marginTop, SPACING_RATIO, MIN_MARGIN);
                    }
                    if (style.marginBottom) {
                        input.style.marginBottom = reduceSpacing(style.marginBottom, SPACING_RATIO, MIN_MARGIN);
                    }
                });
            }
    """


