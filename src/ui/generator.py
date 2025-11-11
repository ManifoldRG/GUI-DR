"""
JavaScript Generator - Generates the main JavaScript injection code.
Extracted from ui_injection.py for better modularity.
"""

import re
from .templates import STYLE_CSS_MAP

# Common CSS base that prevents text overflow and ensures visibility
COMMON_BASE_CSS = """
        /* Preserve original button text - allow full text display */
        button, input[type="button"], input[type="submit"], .btn {
            box-sizing: border-box !important;
            /* Allow text to wrap if needed to show full content */
            white-space: normal !important;
            /* Remove text truncation - show full text */
            overflow: visible !important;
            text-overflow: clip !important;
            /* Allow buttons to size naturally to fit content */
            width: auto !important;
            min-width: fit-content !important;
            max-width: none !important;
            /* Allow buttons to wrap to new line if needed to prevent overlap */
            flex-shrink: 0 !important;
            /* Ensure buttons don't overlap - add spacing */
            margin: 2px 4px !important;
        }
        
        /* Prevent overlapping - ensure proper text wrapping and container expansion */
        * {
            box-sizing: border-box !important;
        }
        
        /* Allow text to wrap naturally but prevent inappropriate breaking */
        p, span, div, h1, h2, h3, h4, h5, h6, li, td, th, label {
            overflow-wrap: break-word !important;
            word-break: normal !important;
            hyphens: auto !important;
            white-space: normal !important;
        }
        
        /* Prevent inline elements from breaking inappropriately */
        a, span, em, strong, i, b, u, small {
            white-space: normal !important;
            word-break: normal !important;
        }
        
        /* Ensure flex/grid containers can expand and wrap */
        nav, header, section, article, aside, main, footer, ul, ol, div[class*="menu"], div[class*="nav"], div[class*="bar"] {
            min-width: 0 !important;
            overflow: visible !important;
        }
        
        /* Prevent button containers from causing overlap - allow wrapping for specific containers only */
        nav, header, [class*="menu"], [class*="nav"], [class*="bar"] {
            flex-wrap: wrap !important;
            gap: 4px 8px !important;
        }
        
        nav button, nav a, header button, header a, [class*="menu"] button, [class*="menu"] a, [class*="nav"] button, [class*="nav"] a {
            /* Allow full text display - preserve original button text */
            flex-shrink: 0 !important;
            min-width: fit-content !important;
            max-width: none !important;
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: clip !important;
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
                
                /* Base body styling - preserve original typography, only change colors and font family */
                body {{
                    background: ${{params.bgColor}} !important;
                    color: ${{params.textColor}} !important;
                    font-family: ${{params.bodyFont}} !important;
                    /* Preserve original font-size, font-weight, line-height, letter-spacing from MHTML */
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
                
                /* Headings styling - preserve original typography, only change colors and font family */
                h1, h2, h3, h4, h5, h6 {{
                    font-family: ${{params.headingFont}} !important;
                    color: ${{params.headingColor}} !important;
                    /* Preserve original font-size, font-weight, line-height, letter-spacing from MHTML */
                    margin: 0.5em 0 !important;
                }}
                
                /* Buttons styling - preserve original typography and dimensions, only change colors and font family */
                button, input[type="button"], input[type="submit"], .btn {{
                    background: ${{params.btnBg}} !important;
                    color: ${{params.btnTextColor}} !important;
                    font-family: ${{params.bodyFont}} !important;
                    /* Preserve original font-size, font-weight, line-height, letter-spacing, padding from MHTML */
                    transition: all ${{params.transitionSpeed}}s ease !important;
                    cursor: pointer !important;
                    text-transform: none !important;
                    text-align: center !important;
                    display: inline-flex !important;
                    align-items: center !important;
                    justify-content: center !important;
                    vertical-align: middle !important;
                    /* Preserve full text display - allow buttons to show complete text */
                    flex-shrink: 0 !important;
                    min-width: fit-content !important;
                    max-width: none !important;
                    white-space: normal !important;
                    overflow: visible !important;
                    text-overflow: clip !important;
                    margin: 2px 4px !important;
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
                
                /* Links styling - preserve original typography, only change colors */
                a {{
                    color: ${{params.linkColor}} !important;
                    /* Preserve original font-weight, font-size, line-height, letter-spacing from MHTML */
                    text-decoration: none !important;
                    transition: all ${{params.transitionSpeed}}s ease !important;
                    border-bottom: 2px solid transparent !important;
                }}
                a:hover {{
                    text-decoration: underline !important;
                    border-bottom-color: ${{params.linkColor}} !important;
                    filter: brightness(1.2) !important;
                }}
                
                /* Input fields styling - preserve original typography, only change colors, font family, and borders */
                input, textarea, select {{
                    background: ${{params.inputBg}} !important;
                    color: ${{params.inputTextColor}} !important;
                    border: ${{params.inputBorderWidth}}px solid ${{params.inputBorderColor}} !important;
                    border-radius: ${{params.inputBorderRadius}}px !important;
                    padding: ${{params.inputPaddingY}}px ${{params.inputPaddingX}}px !important;
                    font-family: ${{params.bodyFont}} !important;
                    /* Preserve original font-size, font-weight, line-height, letter-spacing from MHTML */
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
                    /* Preserve original line-height from MHTML */
                    height: auto !important;
                    min-height: 24px !important;
                    vertical-align: middle !important;
                    display: block !important;
                }}
                select option:checked {{
                    background: ${{params.primaryColor}} !important;
                    color: ${{params.btnTextColor}} !important;
                }}
                
                /* Labels styling - preserve original typography, only change colors and font family */
                label {{
                    color: ${{params.textColor}} !important;
                    font-family: ${{params.bodyFont}} !important;
                    /* Preserve original font-size, font-weight, line-height, letter-spacing from MHTML */
                    margin-bottom: 0.5em !important;
                    display: block !important;
                }}
                
                /* ALL text elements - apply font-family and colors */
                /* JavaScript will ensure proper contrast */
                p, span, div, li, td, th, article, section, main, aside, blockquote, figcaption, caption, dd, dt,
                nav, header, footer, ul, ol, dl, menu, menuitem, summary, details, time, mark, small, sub, sup, del, ins,
                code, pre, samp, kbd, var, output, meter, progress {{
                    font-family: ${{params.bodyFont}} !important;
                    /* Color will be set by JavaScript based on actual background */
                }}
                
                /* Navigation, header, footer - apply background colors and visual styles */
                nav {{
                    background: ${{params.navBg}} !important;
                    border: ${{params.containerBorderWidth}}px solid ${{params.containerBorderColor}} !important;
                    border-radius: ${{params.containerBorderRadius}}px !important;
                    box-shadow: ${{params.containerShadowX}}px ${{params.containerShadowY}}px ${{params.containerShadowBlur}}px ${{params.containerShadowColor}} !important;
                    /* Preserve all layout properties (width, height, padding, margin, display, position) */
                }}
                
                header {{
                    background: ${{params.headerBg}} !important;
                    border: ${{params.containerBorderWidth}}px solid ${{params.containerBorderColor}} !important;
                    border-radius: ${{params.containerBorderRadius}}px !important;
                    box-shadow: ${{params.containerShadowX}}px ${{params.containerShadowY}}px ${{params.containerShadowBlur}}px ${{params.containerShadowColor}} !important;
                    /* Preserve all layout properties */
                }}
                
                footer {{
                    background: ${{params.footerBg}} !important;
                    border: ${{params.containerBorderWidth}}px solid ${{params.containerBorderColor}} !important;
                    border-radius: ${{params.containerBorderRadius}}px !important;
                    box-shadow: ${{params.containerShadowX}}px ${{params.containerShadowY}}px ${{params.containerShadowBlur}}px ${{params.containerShadowColor}} !important;
                    /* Preserve all layout properties */
                }}
                
                /* Sections and articles - apply background colors and visual styles */
                section, article {{
                    background: ${{params.sectionBg}} !important;
                    border: ${{params.containerBorderWidth}}px solid ${{params.containerBorderColor}} !important;
                    border-radius: ${{params.containerBorderRadius}}px !important;
                    box-shadow: ${{params.containerShadowX}}px ${{params.containerShadowY}}px ${{params.containerShadowBlur}}px ${{params.containerShadowColor}} !important;
                    /* Preserve all layout properties */
                }}
                
                /* Main content area */
                main {{
                    background: ${{params.sectionBg}} !important;
                    border: ${{params.containerBorderWidth}}px solid ${{params.containerBorderColor}} !important;
                    border-radius: ${{params.containerBorderRadius}}px !important;
                    box-shadow: ${{params.containerShadowX}}px ${{params.containerShadowY}}px ${{params.containerShadowBlur}}px ${{params.containerShadowColor}} !important;
                    /* Preserve all layout properties */
                }}
                
                /* Aside elements */
                aside {{
                    background: ${{params.sectionBg}} !important;
                    border: ${{params.containerBorderWidth}}px solid ${{params.containerBorderColor}} !important;
                    border-radius: ${{params.containerBorderRadius}}px !important;
                    box-shadow: ${{params.containerShadowX}}px ${{params.containerShadowY}}px ${{params.containerShadowBlur}}px ${{params.containerShadowColor}} !important;
                    /* Preserve all layout properties */
                }}
                
                /* Common container divs with class patterns - apply subtle styling */
                div[class*="card"], div[class*="Card"], div[class*="container"], div[class*="Container"],
                div[class*="box"], div[class*="Box"], div[class*="panel"], div[class*="Panel"],
                div[class*="section"], div[class*="Section"], div[class*="block"], div[class*="Block"] {{
                    background: ${{params.cardBg}} !important;
                    border: ${{params.cardBorderWidth}}px solid ${{params.containerBorderColor}} !important;
                    border-radius: ${{params.cardBorderRadius}}px !important;
                    box-shadow: 0 0 ${{params.cardShadowBlur}}px ${{params.cardShadowColor}} !important;
                    /* Preserve all layout properties */
                }}
                
                /* Strong visual distinction for form elements */
                form {{
                    background: transparent !important;
                }}
                
                /* Note: Container wrapping is handled by JavaScript to avoid breaking layouts */
                /* JavaScript will intelligently convert containers to flex only when needed */
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
                
                // Fix text contrast for ALL elements on the page based on their actual background
                // This is comprehensive - handles all elements including form controls, containers, text elements, etc.
                function fixAllElementTextContrast() {{
                    // Create or get style element for placeholder fixes
                    const styleId = 'text-contrast-fix-placeholders';
                    let styleEl = document.getElementById(styleId);
                    if (!styleEl) {{
                        styleEl = document.createElement('style');
                        styleEl.id = styleId;
                        document.head.appendChild(styleEl);
                    }}
                    
                    // Clear existing placeholder rules
                    while (styleEl.sheet && styleEl.sheet.cssRules.length > 0) {{
                        styleEl.sheet.deleteRule(0);
                    }}
                    
                    let placeholderRuleIndex = 0;
                    
                    // Process ALL elements on the page
                    const allElements = document.querySelectorAll('*');
                    
                    allElements.forEach((el, index) => {{
                        // Skip script and style elements
                        if (el.tagName === 'SCRIPT' || el.tagName === 'STYLE') return;
                        
                        // Skip SVG elements (handled separately for icons)
                        if (el.tagName === 'SVG' || el.tagName === 'PATH' || el.tagName === 'POLYGON' || 
                            el.tagName === 'CIRCLE' || el.tagName === 'RECT' || el.tagName === 'LINE' || el.tagName === 'G') {{
                            return;
                        }}
                        
                        // Get the actual background color of this element
                        const bgRgb = getBackgroundColor(el);
                        if (!bgRgb) return;
                        
                        const bgLum = getLuminance(bgRgb);
                        const textColor = bgLum > 0.5 ? darkText : lightText;
                        
                        // Check if element can contain text or has text content
                        const isTextElement = ['P', 'SPAN', 'DIV', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 
                                             'LI', 'TD', 'TH', 'LABEL', 'A', 'SECTION', 'ARTICLE', 'ASIDE', 
                                             'MAIN', 'HEADER', 'FOOTER', 'NAV', 'EM', 'STRONG', 'SMALL', 'CODE', 
                                             'PRE', 'DD', 'DT', 'BLOCKQUOTE', 'FIGCAPTION', 'CAPTION',
                                             'B', 'I', 'U', 'MARK', 'SUB', 'SUP', 'DEL', 'INS', 'UL', 'OL', 'DL',
                                             'MENU', 'MENUITEM', 'SUMMARY', 'DETAILS', 'TIME', 'OUTPUT', 
                                             'METER', 'PROGRESS', 'SAMP', 'KBD', 'VAR', 'BUTTON', 'INPUT', 
                                             'TEXTAREA', 'SELECT', 'OPTION'].includes(el.tagName);
                        
                        const hasTextContent = el.textContent && el.textContent.trim();
                        const hasDirectText = Array.from(el.childNodes).some(node => 
                            node.nodeType === Node.TEXT_NODE && node.textContent.trim()
                        );
                        const hasValue = el.value && el.value.trim && el.value.trim();
                        const hasPlaceholder = el.placeholder && el.placeholder.trim();
                        
                        // Special handling for buttons - ALWAYS fix based on their actual background
                        if (el.tagName === 'BUTTON' || (el.tagName === 'INPUT' && (el.type === 'button' || el.type === 'submit'))) {{
                            // Get button's actual background (may have been set by CSS or params)
                            const btnBgRgb = getBackgroundColor(el);
                            if (btnBgRgb) {{
                                const btnBgLum = getLuminance(btnBgRgb);
                                const btnTextColor = btnBgLum > 0.5 ? darkText : lightText;
                                // Force button text color with !important
                                el.style.setProperty('color', btnTextColor, 'important');
                                // Also fix any child elements (like icons or spans inside buttons)
                                el.querySelectorAll('*').forEach(child => {{
                                    child.style.setProperty('color', btnTextColor, 'important');
                                }});
                            }}
                            return; // Skip further processing for buttons
                        }}
                        
                        // Fix text color for any element that can have text
                        if (isTextElement || hasTextContent || hasDirectText || hasValue || hasPlaceholder) {{
                            // Set color with !important to override any CSS
                            el.style.setProperty('color', textColor, 'important');
                            
                            // Special handling for input/textarea placeholders
                            if ((el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') && hasPlaceholder) {{
                                // Assign unique ID if needed for placeholder styling
                                if (!el.id) {{
                                    el.id = `input-placeholder-${{index}}-${{Date.now()}}`;
                                }}
                                
                                // Add placeholder color rule
                                try {{
                                    styleEl.sheet?.insertRule(
                                        `#${{el.id}}::placeholder {{ color: ${{textColor}} !important; opacity: 0.7 !important; }}`,
                                        placeholderRuleIndex++
                                    );
                                }} catch (e) {{
                                    console.debug('Could not set placeholder color via CSS rule:', e);
                                }}
                            }}
                            
                            // Special handling for select options
                            if (el.tagName === 'OPTION') {{
                                const selectBg = getBackgroundColor(el.parentElement);
                                if (selectBg) {{
                                    const selectBgLum = getLuminance(selectBg);
                                    el.style.setProperty('background-color', el.selected ? 
                                        (selectBgLum > 0.5 ? '#333333' : '#FFFFFF') : 
                                        (selectBgLum > 0.5 ? '#FFFFFF' : '#1A1A1A'), 'important');
                                    el.style.lineHeight = '1.4';
                                    el.style.padding = '6px 12px';
                                }}
                            }}
                        }}
                    }});
                }}
                
                // Run the comprehensive fix
                fixAllElementTextContrast();
            }}
            
            // Run immediately and also after a short delay to ensure styles are applied
            ensureReadableText();
            setTimeout(ensureReadableText, 50);
            setTimeout(ensureReadableText, 200);
            // Also run on any dynamic content changes
            new MutationObserver(() => {{
                setTimeout(ensureReadableText, 50);
            }}).observe(document.body, {{ childList: true, subtree: true }});
            
            // Apply button colors - but let contrast fix override if needed
            // The contrast fix will ensure proper contrast even if params have issues
            document.querySelectorAll('button, input[type="button"], input[type="submit"]').forEach(el => {{
                el.style.backgroundColor = params.btnBg;
                el.style.color = params.btnTextColor;
                el.style.transition = `all ${{params.transitionSpeed}}s ease`;
                // The fixAllElementTextContrast() function will ensure proper contrast
                // It runs after this, so it will override if needed
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

