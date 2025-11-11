"""
Nearest Element Finder - Finds the closest interactable element to a given target element.

Given a found target element, finds the nearest interactable element and provides
information about their relative positions.
"""

from typing import Dict, Optional, List
from loguru import logger


class NearestElementFinder:
    """Finds the nearest interactable element to a given target element."""
    
    def __init__(self, max_distance: int = 500):
        """
        Initialize the nearest element finder.
        
        Args:
            max_distance: Maximum distance in pixels to consider for "nearby" elements
        """
        self.max_distance = max_distance
    
    async def find_nearest_interactable(
        self, 
        page, 
        target_element_locator,
        prefer_below: bool = True
    ) -> Optional[Dict]:
        """
        Find the nearest interactable element to the target element.
        
        Args:
            page: Playwright page object
            target_element_locator: Playwright locator for the target element
            prefer_below: If True, prefer elements below the target (default: True)
        
        Returns:
            Dict with keys:
                - 'element': Playwright locator (None if not found)
                - 'bbox': Dict with x, y, width, height
                - 'tag': Element tag name
                - 'text': Element text content
                - 'distance': Center-to-center distance in pixels
                - 'relative_position': List of position strings (e.g., ['below', 'right'])
                - 'center_distance': Original center-to-center distance
        """
        try:
            target_element_handle = await target_element_locator.element_handle()
            
            # Use JavaScript to find all interactable elements and calculate distances
            nearest_element_data = await page.evaluate("""
                ({targetEl, maxDistance, preferBelow}) => {
                    const targetRect = targetEl.getBoundingClientRect();
                    const targetArea = targetRect.width * targetRect.height;
                    
                    // Get scroll offsets for full page coordinate conversion
                    const scrollX = window.scrollX || window.pageXOffset || 0;
                    const scrollY = window.scrollY || window.pageYOffset || 0;
                    
                    // Helper function to check if element is an ancestor
                    function isAncestor(el, target) {
                        let parent = target.parentElement;
                        while (parent) {
                            if (parent === el) return true;
                            parent = parent.parentElement;
                        }
                        return false;
                    }
                    
                    // Helper function to check if element is interactable
                    function isInteractable(el) {
                        const tagName = el.tagName.toLowerCase();
                        
                        // Check for interactive HTML tags
                        const interactiveTags = ['button', 'a', 'input', 'select', 'textarea', 'label'];
                        if (interactiveTags.includes(tagName)) {
                            if (tagName === 'input' && el.type === 'hidden') {
                                return false;
                            }
                            return true;
                        }
                        
                        // Check for ARIA roles
                        const role = el.getAttribute('role');
                        const interactiveRoles = ['button', 'link', 'textbox', 'searchbox', 'combobox', 
                                                  'checkbox', 'radio', 'menuitem', 'tab', 'option'];
                        if (role && interactiveRoles.includes(role.toLowerCase())) {
                            return true;
                        }
                        
                        // Check for onclick handlers
                        if (el.onclick || el.getAttribute('onclick')) {
                            return true;
                        }
                        
                        // Check for tabindex (focusable elements)
                        const tabIndex = el.getAttribute('tabindex');
                        if (tabIndex !== null && parseInt(tabIndex) >= 0) {
                            return true;
                        }
                        
                        // Check computed style for cursor pointer
                        const style = window.getComputedStyle(el);
                        if (style.cursor === 'pointer' || style.cursor === 'grab') {
                            return true;
                        }
                        
                        // Check for clickable SVG elements
                        if (tagName === 'svg' || tagName === 'path' || tagName === 'g') {
                            if (el.onclick || el.getAttribute('onclick') || 
                                el.closest('button') || el.closest('a')) {
                                return true;
                            }
                        }
                        
                        // Check for elements with href attribute
                        if (el.href || el.getAttribute('href')) {
                            return true;
                        }
                        
                        return false;
                    }
                    
                    // Get all elements in the document
                    const allElements = document.querySelectorAll('*');
                    const candidateElements = [];
                    
                    for (const el of allElements) {
                        // Skip if it's the target element itself
                        if (el === targetEl) {
                            continue;
                        }
                        
                        // Skip if element is an ancestor of target
                        if (isAncestor(el, targetEl)) {
                            continue;
                        }
                        
                        // Skip if target is an ancestor of this element
                        if (targetEl.contains(el)) {
                            continue;
                        }
                        
                        // Only consider interactable elements
                        if (!isInteractable(el)) {
                            continue;
                        }
                        
                        // Skip if element is not visible
                        const rect = el.getBoundingClientRect();
                        if (rect.width === 0 && rect.height === 0) {
                            continue;
                        }
                        
                        // Filter out very large elements (likely containers)
                        const elArea = rect.width * rect.height;
                        if (elArea > targetArea * 10) {
                            continue;
                        }
                        
                        // Calculate center-to-center distance
                        const targetCenterX = targetRect.left + targetRect.width / 2;
                        const targetCenterY = targetRect.top + targetRect.height / 2;
                        const elCenterX = rect.left + rect.width / 2;
                        const elCenterY = rect.top + rect.height / 2;
                        
                        const dx = elCenterX - targetCenterX;
                        const dy = elCenterY - targetCenterY;
                        const centerDistance = Math.sqrt(dx * dx + dy * dy);
                        
                        // Skip if too far
                        if (centerDistance > maxDistance) {
                            continue;
                        }
                        
                        // Skip if boxes significantly overlap (likely containers)
                        const horizontalOverlap = !(rect.right < targetRect.left || rect.left > targetRect.right);
                        const verticalOverlap = !(rect.bottom < targetRect.top || rect.top > targetRect.bottom);
                        
                        if (horizontalOverlap && verticalOverlap) {
                            const overlapWidth = Math.min(rect.right, targetRect.right) - Math.max(rect.left, targetRect.left);
                            const overlapHeight = Math.min(rect.bottom, targetRect.bottom) - Math.max(rect.top, targetRect.top);
                            const overlapArea = overlapWidth * overlapHeight;
                            const smallerArea = Math.min(elArea, targetArea);
                            
                            if (overlapArea > smallerArea * 0.5) {
                                continue;
                            }
                        }
                        
                        // Calculate relative position of nearest element to target (for distance weighting)
                        const nearestIsBelow = rect.top > targetRect.bottom;
                        const nearestIsAbove = rect.bottom < targetRect.top;
                        const nearestIsLeft = rect.right < targetRect.left;
                        const nearestIsRight = rect.left > targetRect.right;
                        
                        // Calculate weighted distance - prefer elements below if preferBelow is true
                        let weightedDistance = centerDistance;
                        if (preferBelow) {
                            if (nearestIsBelow) {
                                weightedDistance = centerDistance * 0.8;  // Prefer elements below
                            } else if (nearestIsAbove) {
                                weightedDistance = centerDistance * 1.3;  // Deprioritize elements above
                            }
                        }
                        
                        // Get element info
                        const tagName = el.tagName.toLowerCase();
                        let text = '';
                        try {
                            text = el.innerText || el.textContent || '';
                            text = text.trim().substring(0, 100);
                        } catch (e) {}
                        
                        // Build relative position list: TARGET element's position relative to NEAREST element
                        // If nearest element is below target, then target is above nearest
                        const relativePosition = [];
                        if (nearestIsBelow) relativePosition.push('above');  // Target is above nearest
                        if (nearestIsAbove) relativePosition.push('below');  // Target is below nearest
                        if (nearestIsLeft) relativePosition.push('right');    // Target is right of nearest
                        if (nearestIsRight) relativePosition.push('left');   // Target is left of nearest
                        if (relativePosition.length === 0) {
                            relativePosition.push('near');  // Overlapping or very close
                        }
                        
                        candidateElements.push({
                            tag: tagName,
                            text: text,
                            distance: weightedDistance,
                            centerDistance: centerDistance,
                            x: rect.left + scrollX,
                            y: rect.top + scrollY,
                            width: rect.width,
                            height: rect.height,
                            area: elArea,
                            relativePosition: relativePosition
                        });
                    }
                    
                    // Sort by weighted distance first, then prefer elements below target, then by area
                    candidateElements.sort((a, b) => {
                        if (Math.abs(a.distance - b.distance) > 5) {
                            return a.distance - b.distance;
                        }
                        // If distances are very close, prefer elements below target (target above nearest)
                        const aTargetAbove = a.relativePosition.includes('above');
                        const bTargetAbove = b.relativePosition.includes('above');
                        if (aTargetAbove && !bTargetAbove) return -1;
                        if (!aTargetAbove && bTargetAbove) return 1;
                        // Prefer smaller element
                        return a.area - b.area;
                    });
                    
                    return candidateElements.length > 0 ? candidateElements[0] : null;
                }
            """, {
                "targetEl": target_element_handle,
                "maxDistance": self.max_distance,
                "preferBelow": prefer_below
            })
            
            if not nearest_element_data:
                logger.debug("No nearest interactable element found")
                return None
            
            # Convert to page coordinates for bounding box
            return {
                'element': None,  # We don't need the locator for logging
                'bbox': {
                    'x': nearest_element_data['x'],
                    'y': nearest_element_data['y'],
                    'width': nearest_element_data['width'],
                    'height': nearest_element_data['height']
                },
                'tag': nearest_element_data['tag'],
                'text': nearest_element_data['text'],
                'distance': nearest_element_data['distance'],
                'center_distance': nearest_element_data['centerDistance'],
                'relative_position': nearest_element_data['relativePosition']
            }
            
        except Exception as e:
            logger.debug(f"Error finding nearest interactable element: {e}")
            return None

    def log_nearest_element_info(
        self, 
        target_element_text: str,
        nearest_element_info: Optional[Dict]
    ) -> None:
        """
        Log information about the nearest element and relative position.
        
        Args:
            target_element_text: Text content of the target element
            nearest_element_info: Dict returned from find_nearest_interactable()
        """
        if not nearest_element_info:
            logger.info(f"Target element '{target_element_text}': No nearest interactable element found")
            return
        
        relative_pos_str = ', '.join(nearest_element_info['relative_position'])
        nearest_text = nearest_element_info['text'][:50] if nearest_element_info['text'] else '(no text)'
        
        logger.info(
            f"Target element '{target_element_text}': "
            f"Nearest interactable element is {relative_pos_str} - "
            f"tag: {nearest_element_info['tag']}, "
            f"text: '{nearest_text}', "
            f"distance: {nearest_element_info['center_distance']:.1f}px"
        )

