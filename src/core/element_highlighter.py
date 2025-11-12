"""
Element Highlighter - Debug utilities for visually highlighting elements.

Provides visual debugging aids to highlight found elements and original bounding boxes.
"""


class ElementHighlighter:
    """Provides visual debugging aids for elements."""
    
    def __init__(self, page):
        self.page = page
    
    async def highlight_element(self, element_locator):
        """Debug helper: Visually highlight the found element on the page."""
        try:
            await element_locator.evaluate("""
                el => {
                    if (el) {
                        el.style.outline = '4px solid #FF0000';
                        el.style.outlineOffset = '2px';
                        el.style.boxShadow = '0 0 10px rgba(255, 0, 0, 0.5)';
                        el.style.zIndex = '999999';
                    }
                }
            """)
        except Exception as e:
            print(f"⚠️ Could not highlight element: {e}")

    async def highlight_original_box(self, original_box):
        """Debug helper: Visually highlight the original bounding box from pos_candidate.
        
        The original_box coordinates are in document coordinates, so we use absolute positioning
        relative to the document body to show the ground truth location.
        """
        if not original_box:
            return
        
        try:
            await self.page.evaluate("""
                ({x, y, width, height}) => {
                    const existing = document.getElementById('debug-original-box-overlay');
                    if (existing) existing.remove();
                    
                    const overlay = document.createElement('div');
                    overlay.id = 'debug-original-box-overlay';
                    Object.assign(overlay.style, {
                        position: 'absolute',
                        left: x + 'px',
                        top: y + 'px',
                        width: width + 'px',
                        height: height + 'px',
                        border: '3px dashed #00FF00',
                        backgroundColor: 'rgba(0, 255, 0, 0.1)',
                        pointerEvents: 'none',
                        zIndex: '999998',
                        boxSizing: 'border-box'
                    });
                    // Ensure body has relative positioning for absolute children
                    if (document.body.style.position !== 'relative' && document.body.style.position !== 'absolute') {
                        document.body.style.position = 'relative';
                    }
                    document.body.appendChild(overlay);
                }
            """, original_box)
        except Exception as e:
            print(f"⚠️ Could not highlight original box: {e}")

