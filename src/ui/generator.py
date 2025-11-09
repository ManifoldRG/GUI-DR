"""
JavaScript Generator - Generates the main JavaScript injection code.
Extracted from ui_injection.py for better modularity.
"""

import re
from .templates import STYLE_CSS_MAP

# Common CSS base that prevents text overflow and ensures visibility
COMMON_BASE_CSS = """
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


def generate_style_js(params: dict, common_base: str, style_css_template: str) -> str:
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
                /* Set initial color, but JavaScript will fix it based on actual backgrounds */
                body {{
                    color: ${{params.textColor}} !important;
                }}
                
                /* Ensure all text elements can be overridden by JavaScript */
                /* Don't force color on containers - let JS fix based on actual background */
                p, span, div, section, article, aside, main, header, footer {{
                    /* Color will be dynamically set by JavaScript based on actual background */
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
                /* Note: We don't force color here - let JavaScript fix it based on actual background */
                p, span, div {{
                    /* Color will be set by JavaScript based on actual background */
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
                const hexMatch = colorStr.match(/#([0-9a-fA-F]{{6}})/);
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
                
                // Fix text contrast for ALL elements that could contain text
                // This is more aggressive - we fix all containers, not just those with text
                // This ensures nested sections with different backgrounds get the right text color
                function fixAllTextElements() {{
                    // Select all possible text containers and text elements
                    const allElements = document.querySelectorAll('*');
                    
                    allElements.forEach(el => {{
                        // Skip form controls and their children (handled separately)
                        if (el.tagName === 'BUTTON' || el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT') return;
                        if (el.closest('button, input[type="button"], input[type="submit"]')) return;
                        if (el.closest('input, textarea, select')) return;
                        
                        // Skip links inside buttons
                        if (el.tagName === 'A' && el.closest('button')) return;
                        
                        // Skip script and style elements
                        if (el.tagName === 'SCRIPT' || el.tagName === 'STYLE') return;
                        
                        // Get the actual background color of this element
                        const bgRgb = getBackgroundColor(el);
                        if (!bgRgb) return;
                        
                        const bgLum = getLuminance(bgRgb);
                        const textColor = bgLum > 0.5 ? darkText : lightText;
                        
                        // Only fix elements that could contain text or are text containers
                        // This includes: text elements, containers, and any element with text content
                        const isTextElement = ['P', 'SPAN', 'DIV', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 
                                             'LI', 'TD', 'TH', 'LABEL', 'A', 'SECTION', 'ARTICLE', 'ASIDE', 
                                             'MAIN', 'HEADER', 'FOOTER', 'EM', 'STRONG', 'SMALL', 'CODE', 
                                             'PRE', 'DD', 'DT', 'BLOCKQUOTE', 'FIGCAPTION', 'CAPTION',
                                             'B', 'I', 'U', 'MARK', 'SUB', 'SUP', 'DEL', 'INS'].includes(el.tagName);
                        
                        const hasTextContent = el.textContent && el.textContent.trim();
                        const hasDirectText = Array.from(el.childNodes).some(node => 
                            node.nodeType === Node.TEXT_NODE && node.textContent.trim()
                        );
                        
                        // Fix color if it's a text element, has text content, or is a container that might have text
                        if (isTextElement || hasTextContent || hasDirectText) {{
                            // Set color with !important to override any CSS
                            el.style.setProperty('color', textColor, 'important');
                        }}
                    }});
                }}
                
                // Run the fix
                fixAllTextElements();
            }}
            
            // Run immediately and also after a short delay to ensure styles are applied
            ensureReadableText();
            setTimeout(ensureReadableText, 50);
            setTimeout(ensureReadableText, 200);
            // Also run on any dynamic content changes
            new MutationObserver(() => {{
                setTimeout(ensureReadableText, 50);
            }}).observe(document.body, {{ childList: true, subtree: true }});
            
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

