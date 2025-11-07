"""
Element Type Resolver - Resolves element types and finds parent elements.

Handles element type matching (including ARIA roles) and finding parent elements
when child elements are found instead of the target element.
"""

from typing import List, Optional


class ElementTypeResolver:
    """Resolves element types and finds correct parent elements."""
    
    def __init__(self, page):
        self.page = page
    
    async def ensure_correct_element_type(self, element, target_element_type: str):
        """Ensure we have the correct element type, finding parent if needed.
        
        For example, if we need a 'link' but found a 'span' inside the link,
        traverse up to find the parent 'a' element.
        Also handles custom elements (like ry-spinner inside button).
        """
        try:
            tag_name = await element.evaluate("el => el.tagName.toLowerCase()")
            type_lower = target_element_type.lower()
            
            # If 'generic', accept any tag
            if type_lower == 'generic':
                return element
            
            # Check if current element matches expected type (including ARIA roles)
            if await self.element_matches_type(element, type_lower, tag_name):
                return element
            
            # If not, try to find parent element of correct type
            # First try by expected tags
            expected_tags = self._get_expected_tags_for_type(type_lower)
            if expected_tags:
                parent = await self._find_parent_of_type(element, expected_tags)
                if parent:
                    # Verify parent matches type (including ARIA roles)
                    parent_tag = await parent.evaluate("el => el.tagName.toLowerCase()")
                    if await self.element_matches_type(parent, type_lower, parent_tag):
                        print(f"  📌 Found parent element of type '{target_element_type}'")
                        return parent
            
            # For button type, also try finding by ARIA role or button tag (handles custom elements)
            if type_lower == 'button':
                # Try by role first
                parent = await self._find_parent_by_role(element, 'button')
                if parent:
                    print(f"  📌 Found parent element with role='button'")
                    return parent
                # Also try finding button tag (for custom elements like ry-spinner inside button)
                parent = await self._find_parent_of_type(element, ['button'])
                if parent:
                    parent_tag = await parent.evaluate("el => el.tagName.toLowerCase()")
                    if await self.element_matches_type(parent, type_lower, parent_tag):
                        print(f"  📌 Found parent button element")
                        return parent
            
            # For link type, also try finding by ARIA role or 'a' tag
            if type_lower == 'link':
                # Try by role first
                parent = await self._find_parent_by_role(element, 'link')
                if parent:
                    print(f"  📌 Found parent element with role='link'")
                    return parent
                # Also try finding 'a' tag
                parent = await self._find_parent_of_type(element, ['a'])
                if parent:
                    parent_tag = await parent.evaluate("el => el.tagName.toLowerCase()")
                    if await self.element_matches_type(parent, type_lower, parent_tag):
                        print(f"  📌 Found parent link element")
                        return parent
            
            # Return original element - validation will catch if it's wrong
            return element
            
        except Exception:
            # If anything fails, return original element - validation will catch issues
            return element
    
    async def element_matches_type(self, element, type_lower: str, tag_name: str) -> bool:
        """Check if element matches the expected type, including ARIA roles."""
        try:
            # Check ARIA role first (for custom elements)
            aria_role = await element.get_attribute('role')
            if aria_role:
                aria_role_lower = aria_role.lower()
                if type_lower == 'button' and aria_role_lower == 'button':
                    return True
                if type_lower == 'radio' and aria_role_lower == 'radio':
                    return True
                if type_lower == 'checkbox' and aria_role_lower == 'checkbox':
                    return True
                if type_lower == 'link' and aria_role_lower == 'link':
                    return True
            
            # Check tag-based matching
            if type_lower == 'link' and tag_name == 'a':
                return True
            elif type_lower == 'button' and tag_name in ('button', 'input'):
                input_type = await element.evaluate("el => el.type || ''")
                if input_type in ('button', 'submit', ''):
                    return True
            elif type_lower in ('input', 'textbox', 'searchbox') and tag_name == 'input':
                input_type = await element.evaluate("el => el.type || ''")
                if type_lower == 'searchbox' and input_type == 'search':
                    return True
                elif type_lower in ('input', 'textbox') and input_type in ('text', 'email', 'password', 'tel', 'url', ''):
                    return True
            elif type_lower == 'combobox' and tag_name == 'select':
                return True
            elif type_lower == 'checkbox' and tag_name == 'input':
                input_type = await element.evaluate("el => el.type || ''")
                if input_type == 'checkbox':
                    return True
            elif type_lower == 'radio' and tag_name == 'input':
                input_type = await element.evaluate("el => el.type || ''")
                if input_type == 'radio':
                    return True
            elif type_lower == 'ins' and tag_name == 'ins':
                return True
            elif type_lower == tag_name:
                # Direct tag match (e.g., 'li', 'div', etc.)
                return True
            
            return False
        except Exception:
            return False
    
    def _get_expected_tags_for_type(self, type_lower: str) -> List[str]:
        """Get expected HTML tags for a given element type."""
        type_to_tags = {
            'link': ['a'],
            'button': ['button', 'input'],
            'input': ['input'],
            'textbox': ['input'],
            'searchbox': ['input'],
            'combobox': ['select'],
            'checkbox': ['input'],
            'radio': ['input'],
        }
        return type_to_tags.get(type_lower, [])
    
    async def _find_parent_of_type(self, element, expected_tags: List[str]) -> Optional:
        """Find parent element that matches one of the expected tag names."""
        try:
            parent = await element.evaluate_handle("""
                (el, expectedTags) => {
                    let current = el;
                    let depth = 0;
                    const maxDepth = 10;
                    
                    while (current && depth < maxDepth) {
                        current = current.parentElement;
                        if (!current) break;
                        
                        const tagName = current.tagName.toLowerCase();
                        if (expectedTags.includes(tagName)) {
                            return current;
                        }
                        
                        depth++;
                    }
                    
                    return null;
                }
            """, expected_tags)
            
            if parent:
                is_valid = await parent.evaluate("el => el !== null && el !== undefined")
                if is_valid:
                    return parent
            
            return None
        except Exception:
            return None
    
    async def _find_parent_by_role(self, element, expected_role: str) -> Optional:
        """Find parent element that has the expected ARIA role."""
        try:
            parent = await element.evaluate_handle("""
                (el, expectedRole) => {
                    let current = el;
                    let depth = 0;
                    const maxDepth = 10;
                    
                    while (current && depth < maxDepth) {
                        current = current.parentElement;
                        if (!current) break;
                        
                        const role = current.getAttribute('role');
                        if (role && role.toLowerCase() === expectedRole.toLowerCase()) {
                            return current;
                        }
                        
                        depth++;
                    }
                    
                    return null;
                }
            """, expected_role)
            
            if parent:
                is_valid = await parent.evaluate("el => el !== null && el !== undefined")
                if is_valid:
                    return parent
            
            return None
        except Exception:
            return None

