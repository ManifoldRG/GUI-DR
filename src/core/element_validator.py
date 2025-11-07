"""
Element Validator - Strict validation of found elements.

Validates that elements match expected type, text, visibility, and bounding box constraints.
"""

from typing import Dict
from exceptions import ElementValidationError
from locators.strategies import normalize_text


class ElementValidator:
    """Validates elements to ensure they match expected criteria."""
    
    def __init__(self, page):
        self.page = page
    
    async def validate_element(self, element, target_element_type: str, target_element_text: str):
        """Strictly validate that the found element matches expected type and text.
        
        Raises:
            ElementValidationError: If element doesn't match expected criteria
        """
        try:
            # Validate element type
            tag_name = await element.evaluate("el => el.tagName.toLowerCase()")
            type_lower = target_element_type.lower()
            
            # 'generic' type matches any tag
            if type_lower == 'generic':
                type_valid = True
            else:
                # Use ElementTypeResolver for type matching
                # Import here to avoid circular dependency
                from core.element_type_resolver import ElementTypeResolver
                resolver = ElementTypeResolver(self.page)
                type_valid = await resolver.element_matches_type(element, type_lower, tag_name)
            
            if not type_valid:
                # Get more info for error message
                aria_role = await element.get_attribute('role') or 'none'
                raise ElementValidationError(
                    f"Element type mismatch: expected '{target_element_type}', found tag '{tag_name}' (role='{aria_role}')"
                )
            
            # Validate element text if provided
            if target_element_text and target_element_text.strip():
                element_text = await element.text_content() or ""
                normalized_element = normalize_text(element_text)
                normalized_target = normalize_text(target_element_text)
                
                # Text should match (substring or contains)
                if normalized_target not in normalized_element and normalized_element not in normalized_target:
                    # Allow empty text for certain element types (like ins, which might be decorative)
                    if type_lower not in ('ins', 'span', 'div'):
                        raise ElementValidationError(
                            f"Element text mismatch: expected '{target_element_text}', found '{element_text[:50]}...'"
                        )
            
            # Validate element is actually attached to DOM
            is_attached = await element.evaluate("el => el.isConnected")
            if not is_attached:
                raise ElementValidationError("Element is not attached to DOM")
                
        except ElementValidationError:
            raise
        except Exception as e:
            raise ElementValidationError(f"Failed to validate element: {e}")
    
    async def validate_after_scroll(self, element, target_element_type: str, target_element_text: str):
        """Strictly validate element after scrolling to ensure it's still correct and visible.
        
        Raises:
            ElementValidationError: If element is invalid or not visible after scrolling
        """
        try:
            # Verify element is still visible
            is_visible = await element.is_visible()
            if not is_visible:
                raise ElementValidationError("Element is not visible after scrolling")
            
            # Verify element is in viewport (not just visible but actually in view)
            in_viewport = await element.evaluate("""
                (el) => {
                    const rect = el.getBoundingClientRect();
                    const viewportWidth = window.innerWidth || document.documentElement.clientWidth;
                    const viewportHeight = window.innerHeight || document.documentElement.clientHeight;
                    
                    // Element must be at least partially in viewport
                    return (
                        rect.top < viewportHeight &&
                        rect.bottom > 0 &&
                        rect.left < viewportWidth &&
                        rect.right > 0 &&
                        rect.width > 0 &&
                        rect.height > 0
                    );
                }
            """)
            
            if not in_viewport:
                raise ElementValidationError("Element is not in viewport after scrolling")
            
            # Re-validate element type/text to ensure we still have the right element
            # (scrolling might have changed the DOM)
            await self.validate_element(element, target_element_type, target_element_text)
            
        except ElementValidationError:
            raise
        except Exception as e:
            raise ElementValidationError(f"Failed to validate element after scroll: {e}")
    
    async def validate_bounding_box(self, bounding_box: Dict[str, float]):
        """Strictly validate bounding box is reasonable and valid.
        
        Raises:
            ElementValidationError: If bounding box is invalid or unreasonable
        """
        try:
            x = bounding_box.get('x', 0)
            y = bounding_box.get('y', 0)
            width = bounding_box.get('width', 0)
            height = bounding_box.get('height', 0)
            
            # Check for valid dimensions
            if width <= 0 or height <= 0:
                raise ElementValidationError(f"Invalid bounding box dimensions: {width}x{height}")
            
            # Check for reasonable size (not too small, not impossibly large)
            if width < 1 or height < 1:
                raise ElementValidationError(f"Bounding box too small: {width}x{height}")
            
            if width > 10000 or height > 10000:
                raise ElementValidationError(f"Bounding box unreasonably large: {width}x{height}")
            
            # Check coordinates are reasonable (not negative beyond reasonable scroll, not impossibly large)
            if x < -1000 or y < -1000:
                raise ElementValidationError(f"Bounding box coordinates out of reasonable range: ({x}, {y})")
            
            if x > 50000 or y > 50000:
                raise ElementValidationError(f"Bounding box coordinates unreasonably large: ({x}, {y})")
            
            # Verify bounding box is in viewport (after scrolling, it should be)
            viewport_info = await self.page.evaluate("""
                () => ({
                    width: window.innerWidth || document.documentElement.clientWidth,
                    height: window.innerHeight || document.documentElement.clientHeight,
                    scrollX: window.scrollX,
                    scrollY: window.scrollY
                })
            """)
            
            # Calculate if bounding box is at least partially in viewport
            bbox_in_viewport = (
                x < viewport_info['width'] + viewport_info['scrollX'] and
                x + width > viewport_info['scrollX'] and
                y < viewport_info['height'] + viewport_info['scrollY'] and
                y + height > viewport_info['scrollY']
            )
            
            if not bbox_in_viewport:
                raise ElementValidationError(
                    f"Bounding box not in viewport after scrolling: ({x}, {y}, {width}, {height})"
                )
                
        except ElementValidationError:
            raise
        except Exception as e:
            raise ElementValidationError(f"Failed to validate bounding box: {e}")

