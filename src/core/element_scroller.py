"""
Element Scroller - Handles scrolling elements into view.

Handles cases where elements are inside scrollable containers (e.g., dropdown menus).
"""

import asyncio


class ElementScroller:
    """Handles scrolling elements into view, including elements in scrollable containers."""
    
    def __init__(self, page):
        self.page = page
    
    async def ensure_element_visible(self, element):
        """Ensure element is visible by scrolling it into view.
        
        Handles cases where element is inside scrollable containers (e.g., dropdown menus).
        Detects if element is in a scrollable container and scrolls both the container and page if needed.
        Uses graceful error handling to avoid timeouts when elements are unstable.
        """
        try:
            # First check if element is already visible - if so, skip scrolling
            try:
                is_visible = await element.is_visible()
                if is_visible:
                    # Check if element is in viewport (not just visible but actually in view)
                    in_viewport = await element.evaluate("""
                        (el) => {
                            const rect = el.getBoundingClientRect();
                            return (
                                rect.top >= 0 &&
                                rect.left >= 0 &&
                                rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
                                rect.right <= (window.innerWidth || document.documentElement.clientWidth)
                            );
                        }
                    """)
                    if in_viewport:
                        # Element is visible and in viewport, no scrolling needed
                        return
            except Exception:
                # If visibility check fails, continue with scrolling attempt
                pass
            
            # Check if element is in a scrollable container (like dropdown menu)
            try:
                is_in_scrollable_container = await element.evaluate("""
                    (el) => {
                        let current = el;
                        let depth = 0;
                        const maxDepth = 10;
                        
                        while (current && depth < maxDepth) {
                            current = current.parentElement;
                            if (!current) break;
                            
                            const style = window.getComputedStyle(current);
                            const overflow = style.overflow || style.overflowY || style.overflowX;
                            const hasScroll = overflow === 'auto' || overflow === 'scroll';
                            
                            // Check if container is scrollable and has scrollable content
                            if (hasScroll) {
                                const scrollHeight = current.scrollHeight;
                                const clientHeight = current.clientHeight;
                                if (scrollHeight > clientHeight) {
                                    return true; // Found scrollable container
                                }
                            }
                            
                            depth++;
                        }
                        
                        return false;
                    }
                """)
            except Exception:
                is_in_scrollable_container = False
            
            # Try Playwright's scroll_into_view_if_needed with shorter timeout
            # Use shorter timeout to avoid waiting too long for unstable elements
            try:
                await asyncio.wait_for(
                    element.scroll_into_view_if_needed(timeout=1000),
                    timeout=1.5
                )
                await asyncio.sleep(0.1)
            except (asyncio.TimeoutError, Exception) as e:
                # If Playwright's method times out (element not stable), use direct JavaScript
                # This is more reliable for elements that are animating or changing
                try:
                    await element.evaluate("""
                        (el) => {
                            // Find scrollable container and scroll it
                            let current = el;
                            let depth = 0;
                            const maxDepth = 10;
                            
                            while (current && depth < maxDepth) {
                                current = current.parentElement;
                                if (!current) break;
                                
                                const style = window.getComputedStyle(current);
                                const overflow = style.overflow || style.overflowY || style.overflowX;
                                const hasScroll = (overflow === 'auto' || overflow === 'scroll') && 
                                                current.scrollHeight > current.clientHeight;
                                
                                if (hasScroll) {
                                    // Scroll container to show element
                                    const containerRect = current.getBoundingClientRect();
                                    const elementRect = el.getBoundingClientRect();
                                    
                                    // Calculate scroll position to center element in container
                                    const scrollTop = current.scrollTop + 
                                        (elementRect.top - containerRect.top) - 
                                        (containerRect.height / 2) + 
                                        (elementRect.height / 2);
                                    
                                    current.scrollTop = Math.max(0, scrollTop);
                                }
                                
                                depth++;
                            }
                            
                            // Also scroll element itself into viewport (use 'auto' for instant scroll)
                            el.scrollIntoView({ behavior: 'auto', block: 'center', inline: 'center' });
                        }
                    """)
                    await asyncio.sleep(0.1)
                except Exception as js_error:
                    # If JavaScript scrolling also fails, try simple scrollIntoView
                    try:
                        await element.evaluate("el => el.scrollIntoView({ behavior: 'auto', block: 'center' })")
                        await asyncio.sleep(0.05)
                    except Exception:
                        # If all scrolling fails, continue anyway - bounding_box() might still work
                        # This is not a critical failure
                        pass
                
        except Exception as e:
            # If any error occurs, log but don't fail - element might still be usable
            # Many elements don't need scrolling and will work fine without it
            pass

