"""
UI Injection Module - Generates JavaScript code for injecting UI modifications
"""
import re


def generate_injection_js(params: dict) -> str:
    """Generate JavaScript code for injecting UI modifications."""
    style = params.get('designStyle', 'modern_minimal')
    
    # Common CSS base that prevents text overflow and ensures visibility
    common_base = """
        /* Prevent text overflow - ensure containers adapt to content */
        button, input[type="button"], input[type="submit"], .btn {
            box-sizing: border-box !important;
            white-space: nowrap !important;
            overflow: visible !important;
            width: auto !important;
            min-width: fit-content !important;
            max-width: 100% !important;
            word-wrap: break-word !important;
            overflow-wrap: break-word !important;
        }
        
        /* Ensure text doesn't overflow containers */
        * {
            box-sizing: border-box !important;
            overflow-wrap: break-word !important;
            word-break: break-word !important;
        }
        
        /* Force visibility for all text and icons - override inherited colors */
        p, span, div, td, th, li, dd, dt, em, strong, small, code, pre {
            color: inherit !important;
        }
        
        /* Ensure icons and SVGs are visible - will be fixed by JS based on background */
        svg, path, polygon, circle, rect, line {
            fill: currentColor !important;
            stroke: currentColor !important;
        }
        
        /* Ensure icon fonts are visible - will be fixed by JS */
        [class*="icon"], [class*="Icon"], i[class], .fa, .fas, .far, .fab {
            color: inherit !important;
        }
    """
    
    if style == 'neobrutalism':
        return _generate_style_js(params, common_base, neobrutalism_css)
    elif style == 'glassmorphism':
        return _generate_style_js(params, common_base, glassmorphism_css)
    elif style == 'neumorphism':
        return _generate_style_js(params, common_base, neumorphism_css)
    elif style == 'retro_vibrant':
        return _generate_style_js(params, common_base, retro_css)
    elif style == 'dark_mode':
        return _generate_style_js(params, common_base, dark_mode_css)
    elif style == 'pastel_dream':
        return _generate_style_js(params, common_base, pastel_css)
    elif style == 'cyberpunk':
        return _generate_style_js(params, common_base, cyberpunk_css)
    else:
        return _generate_style_js(params, common_base, modern_css)


def _generate_style_js(params: dict, common_base: str, style_css_template: str) -> str:
    """Generate JavaScript with common base and style-specific CSS."""
    # Convert Python format placeholders to JavaScript template literals
    style_css = re.sub(r'\{(\w+)\}', r'${params.\1}', style_css_template)
    
    return f"""
        (params) => {{
            const existing = document.getElementById('ui-modifications-style');
            if (existing) existing.remove();
            
            const style = document.createElement('style');
            style.id = 'ui-modifications-style';
            style.textContent = `
                {common_base}
                
                /* Base body with dramatic styling - ensure all text inherits readable color */
                body {{
                    background: ${{params.bgColor}} !important;
                    color: ${{params.textColor}} !important;
                    font-family: ${{params.bodyFont}} !important;
                    font-size: ${{params.bodySize}}px !important;
                    font-weight: ${{params.bodyWeight}} !important;
                    line-height: ${{params.lineHeight}} !important;
                    letter-spacing: ${{params.letterSpacing}}em !important;
                }}
                
                /* Base text color - will be overridden by JS for proper contrast */
                body {{
                    color: ${{params.textColor}} !important;
                }}
                
                /* Headings with dramatic styling */
                h1, h2, h3, h4, h5, h6 {{
                    font-family: ${{params.headingFont}} !important;
                    font-size: ${{params.headingSize}}px !important;
                    font-weight: ${{params.headingWeight}} !important;
                    color: ${{params.headingColor}} !important;
                    letter-spacing: ${{params.letterSpacing}}em !important;
                    margin: 0.5em 0 !important;
                }}
                
                /* Buttons with dramatic styling - fix text alignment */
                button, input[type="button"], input[type="submit"], .btn {{
                    background: ${{params.btnBg}} !important;
                    color: ${{params.btnTextColor}} !important;
                    font-family: ${{params.bodyFont}} !important;
                    font-size: ${{params.bodySize}}px !important;
                    font-weight: ${{params.bodyWeight}} !important;
                    padding: ${{params.btnPaddingY}}px ${{params.btnPaddingX}}px !important;
                    transition: all ${{params.transitionSpeed}}s ease !important;
                    cursor: pointer !important;
                    text-transform: none !important;
                    text-align: center !important;
                    display: inline-flex !important;
                    align-items: center !important;
                    justify-content: center !important;
                    vertical-align: middle !important;
                    line-height: 1 !important;
                    {style_css}
                }}
                /* Ensure button text stays inside */
                button > *, input[type="button"] > *, input[type="submit"] > *, .btn > * {{
                    color: ${{params.btnTextColor}} !important;
                    display: inline-block !important;
                    vertical-align: middle !important;
                }}
                button:hover, input[type="button"]:hover, input[type="submit"]:hover, .btn:hover {{
                    transform: translateY(-2px) !important;
                    filter: brightness(1.1) !important;
                }}
                
                /* Links with dramatic styling */
                a {{
                    color: ${{params.linkColor}} !important;
                    font-weight: ${{params.bodyWeight}} !important;
                    text-decoration: none !important;
                    transition: all ${{params.transitionSpeed}}s ease !important;
                    border-bottom: 2px solid transparent !important;
                }}
                a:hover {{
                    text-decoration: underline !important;
                    border-bottom-color: ${{params.linkColor}} !important;
                    filter: brightness(1.2) !important;
                }}
                
                /* Input fields with dramatic styling */
                input, textarea, select {{
                    background: ${{params.inputBg}} !important;
                    color: ${{params.inputTextColor}} !important;
                    border: ${{params.inputBorderWidth}}px solid ${{params.inputBorderColor}} !important;
                    border-radius: ${{params.inputBorderRadius}}px !important;
                    padding: ${{params.inputPaddingY}}px ${{params.inputPaddingX}}px !important;
                    font-family: ${{params.bodyFont}} !important;
                    font-size: ${{params.bodySize}}px !important;
                    font-weight: ${{params.bodyWeight}} !important;
                    line-height: 1.4 !important;
                    transition: all ${{params.transitionSpeed}}s ease !important;
                    box-sizing: border-box !important;
                    vertical-align: middle !important;
                }}
                input:focus, textarea:focus, select:focus {{
                    outline: 3px solid ${{params.primaryColor}} !important;
                    outline-offset: 2px !important;
                    border-color: ${{params.primaryColor}} !important;
                    box-shadow: 0 0 0 4px ${{params.primaryColor}}33 !important;
                }}
                /* Ensure dropdown options are readable and properly sized */
                select {{
                    height: auto !important;
                    min-height: fit-content !important;
                    overflow: visible !important;
                }}
                select option {{
                    background: ${{params.inputBg}} !important;
                    color: ${{params.inputTextColor}} !important;
                    padding: 6px 12px !important;
                    line-height: 1.4 !important;
                    height: auto !important;
                    min-height: 24px !important;
                    vertical-align: middle !important;
                    display: block !important;
                }}
                select option:checked {{
                    background: ${{params.primaryColor}} !important;
                    color: ${{params.btnTextColor}} !important;
                }}
                
                /* Labels with dramatic styling */
                label {{
                    color: ${{params.textColor}} !important;
                    font-family: ${{params.bodyFont}} !important;
                    font-weight: ${{params.bodyWeight}} !important;
                    font-size: ${{params.bodySize}}px !important;
                    margin-bottom: 0.5em !important;
                    display: block !important;
                }}
                
                /* Additional dramatic styling for common elements */
                p, span, div {{
                    color: ${{params.textColor}} !important;
                }}
                
                /* Strong visual distinction for form elements */
                form {{
                    background: transparent !important;
                }}
            `;
            document.head.appendChild(style);
            
            // Fix text contrast for all elements based on their background
            function getLuminance(rgb) {{
                const [r, g, b] = rgb.map(val => {{
                    val = val / 255;
                    return val <= 0.03928 ? val / 12.92 : Math.pow((val + 0.055) / 1.055, 2.4);
                }});
                return 0.2126 * r + 0.7152 * g + 0.0722 * b;
            }}
            
            function rgbFromString(colorStr) {{
                if (!colorStr || colorStr === 'transparent' || colorStr === 'rgba(0, 0, 0, 0)') return null;
                const match = colorStr.match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)/);
                if (match) return [parseInt(match[1]), parseInt(match[2]), parseInt(match[3])];
                const hexMatch = colorStr.match(/#([0-9a-fA-F]{6})/);
                if (hexMatch) {{
                    const hex = hexMatch[1];
                    return [parseInt(hex.substr(0,2), 16), parseInt(hex.substr(2,2), 16), parseInt(hex.substr(4,2), 16)];
                }}
                return null;
            }}
            
            function getBackgroundColor(el) {{
                const bg = window.getComputedStyle(el).backgroundColor;
                if (bg && bg !== 'transparent' && bg !== 'rgba(0, 0, 0, 0)') return rgbFromString(bg);
                if (el.parentElement) return getBackgroundColor(el.parentElement);
                return [255, 255, 255]; // Default to white
            }}
            
            function ensureReadableText() {{
                const darkText = '#000000';
                const lightText = '#FFFFFF';
                
                // Fix icons and SVGs - ensure they're visible based on container background
                document.querySelectorAll('svg, [class*="icon"], [class*="Icon"], i[class], .fa, .fas, .far, .fab').forEach(icon => {{
                    // Check if icon is inside an input container (like search bars)
                    const inputContainer = icon.closest('input, .input-group, .search-container, [class*="input"]');
                    const containerBg = inputContainer ? getBackgroundColor(inputContainer) : getBackgroundColor(icon);
                    
                    if (containerBg) {{
                        const bgLum = getLuminance(containerBg);
                        const iconColor = bgLum > 0.5 ? darkText : lightText;
                        
                        // Set color for icon fonts
                        if (icon.tagName !== 'svg') {{
                            icon.style.color = iconColor;
                            icon.style.display = 'inline-block';
                        }}
                        
                        // Set fill/stroke for SVG elements
                        if (icon.tagName === 'svg') {{
                            icon.style.fill = iconColor;
                            icon.style.stroke = iconColor;
                            icon.style.display = 'inline-block';
                            icon.querySelectorAll('path, polygon, circle, rect, line, g').forEach(path => {{
                                const fillAttr = path.getAttribute('fill');
                                const strokeAttr = path.getAttribute('stroke');
                                if (!fillAttr || fillAttr === 'currentColor' || fillAttr === 'none') {{
                                    path.style.fill = iconColor;
                                }}
                                if (!strokeAttr || strokeAttr === 'currentColor' || strokeAttr === 'none') {{
                                    path.style.stroke = iconColor;
                                }}
                            }});
                        }}
                    }}
                }});
                
                // Fix background-image icons (like CSS background-image: url(...svg))
                document.querySelectorAll('*').forEach(el => {{
                    const bgImage = window.getComputedStyle(el).backgroundImage;
                    if (bgImage && bgImage !== 'none' && (bgImage.includes('svg') || bgImage.includes('icon') || bgImage.includes('.svg'))) {{
                        const containerBg = getBackgroundColor(el);
                        if (containerBg) {{
                            const bgLum = getLuminance(containerBg);
                            // For dark backgrounds, invert the icon; for light backgrounds, keep original
                            if (bgLum < 0.5) {{
                                el.style.filter = 'invert(1) brightness(1.5)';
                            }} else {{
                                el.style.filter = 'brightness(0.8)';
                            }}
                            // Ensure element is visible
                            el.style.backgroundSize = el.style.backgroundSize || 'contain';
                            el.style.backgroundRepeat = 'no-repeat';
                            el.style.backgroundPosition = 'center';
                        }}
                    }}
                }});
                
                // Fix select dropdown options specifically
                document.querySelectorAll('select option').forEach(opt => {{
                    const selectBg = getBackgroundColor(opt.parentElement);
                    if (selectBg) {{
                        const bgLum = getLuminance(selectBg);
                        opt.style.color = bgLum > 0.5 ? darkText : lightText;
                        opt.style.backgroundColor = opt.selected ? (bgLum > 0.5 ? '#333333' : '#FFFFFF') : (bgLum > 0.5 ? '#FFFFFF' : '#1A1A1A');
                        opt.style.lineHeight = '1.4';
                        opt.style.padding = '6px 12px';
                    }}
                }});
                
                // Select all text elements, excluding form controls and their children
                const allElements = document.querySelectorAll('p, span, div, h1, h2, h3, h4, h5, h6, li, td, th, label, a, section, article, aside, main, header, footer');
                
                allElements.forEach(el => {{
                    // Skip form controls and their children
                    if (el.tagName === 'BUTTON' || el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT') return;
                    if (el.closest('button, input[type="button"], input[type="submit"]')) return;
                    
                    // Skip links inside buttons
                    if (el.tagName === 'A' && el.closest('button')) return;
                    
                    const bgRgb = getBackgroundColor(el);
                    if (!bgRgb) return;
                    const bgLum = getLuminance(bgRgb);
                    
                    // Use dark text on light backgrounds, light text on dark backgrounds
                    const textColor = bgLum > 0.5 ? darkText : lightText;
                    // Only set if element actually contains text
                    if (el.textContent && el.textContent.trim()) {{
                        el.style.color = textColor;
                    }}
                }});
            }}
            
            // Run after a short delay to ensure styles are applied
            setTimeout(ensureReadableText, 100);
            // Also run on any dynamic content changes
            new MutationObserver(ensureReadableText).observe(document.body, {{ childList: true, subtree: true }});
            
            // Apply button colors
            document.querySelectorAll('button, input[type="button"], input[type="submit"]').forEach(el => {{
                el.style.backgroundColor = params.btnBg;
                el.style.color = params.btnTextColor;
                el.style.transition = `all ${{params.transitionSpeed}}s ease`;
            }});
            
            // Reorder DOM elements if enabled and not intentionally alphabetically ordered
            if (params.enableElementReordering) {{
                const allInteractive = Array.from(document.querySelectorAll('button, input[type="button"], input[type="submit"], a'));
                const byParent = new Map();
                allInteractive.forEach(el => {{
                    if (el.parentNode) {{
                        if (!byParent.has(el.parentNode)) byParent.set(el.parentNode, []);
                        byParent.get(el.parentNode).push(el);
                    }}
                }});
                
                byParent.forEach((elements, parent) => {{
                    // Check if elements are intentionally alphabetically ordered
                    const texts = elements.map(el => (el.textContent || el.innerText || '').trim().toLowerCase());
                    const isAlphabetical = texts.length > 1 && texts.every((text, i) => i === 0 || texts[i-1] <= text);
                    
                    // Only reorder if not alphabetically ordered
                    if (!isAlphabetical && elements.length > 1) {{
                        elements.forEach(el => parent.removeChild(el));
                        elements.sort(() => Math.random() - 0.5);
                        elements.forEach(el => parent.appendChild(el));
                    }}
                }});
            }}
        }}
    """


# Style-specific CSS fragments with more dramatic effects
neobrutalism_css = """
                    border: {btnBorderWidth}px solid {btnBorderColor} !important;
                    border-radius: {btnBorderRadius}px !important;
                    box-shadow: {btnShadowX}px {btnShadowY}px {btnShadowBlur}px {btnShadowColor} !important;
                    text-transform: uppercase !important;
                    letter-spacing: 0.1em !important;
"""

glassmorphism_css = """
                    border: {btnBorderWidth}px solid {btnBorderColor} !important;
                    border-radius: {btnBorderRadius}px !important;
                    backdrop-filter: blur({btnBackdropBlur}px) !important;
                    box-shadow: {btnShadowX}px {btnShadowY}px {btnShadowBlur}px {btnShadowColor} !important;
                    background: linear-gradient(135deg, rgba(255,255,255,0.1), rgba(255,255,255,0)) !important;
"""

neumorphism_css = """
                    border: {btnBorderWidth}px solid transparent !important;
                    border-radius: {btnBorderRadius}px !important;
                    box-shadow: {btnShadowLight}, {btnShadowDark} !important;
                    background: {btnBg} !important;
"""

retro_css = """
                    border: {btnBorderWidth}px solid {btnBorderColor} !important;
                    border-radius: {btnBorderRadius}px !important;
                    box-shadow: {btnShadowX}px {btnShadowY}px {btnShadowBlur}px {btnShadowColor} !important;
                    background: linear-gradient(135deg, {btnBg}, {btnBg}dd) !important;
"""

dark_mode_css = """
                    border: {btnBorderWidth}px solid {btnBorderColor} !important;
                    border-radius: {btnBorderRadius}px !important;
                    box-shadow: 0 0 {btnShadowBlur}px {btnShadowColor}, 0 0 {btnShadowBlur}px {btnShadowColor} !important;
                    background: {btnBg} !important;
                    text-shadow: 0 0 10px {btnTextColor} !important;
"""

pastel_css = """
                    border: {btnBorderWidth}px solid {btnBorderColor} !important;
                    border-radius: {btnBorderRadius}px !important;
                    box-shadow: {btnShadowX}px {btnShadowY}px {btnShadowBlur}px {btnShadowColor} !important;
                    background: linear-gradient(135deg, {btnBg}, {btnBg}ee) !important;
"""

cyberpunk_css = """
                    border: {btnBorderWidth}px solid {btnBorderColor} !important;
                    border-radius: {btnBorderRadius}px !important;
                    box-shadow: 0 0 {btnShadowBlur}px {btnShadowColor}, inset 0 0 {btnShadowBlur}px {btnShadowColor} !important;
                    background: {btnBg} !important;
                    text-shadow: 0 0 5px {btnTextColor}, 0 0 10px {btnTextColor} !important;
"""

modern_css = """
                    border: {btnBorderWidth}px solid {btnBorderColor} !important;
                    border-radius: {btnBorderRadius}px !important;
                    box-shadow: {btnShadowX}px {btnShadowY}px {btnShadowBlur}px {btnShadowColor} !important;
                    background: {btnBg} !important;
"""
