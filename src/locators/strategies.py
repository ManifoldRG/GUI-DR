"""
Locator Strategies - Individual strategy classes for finding elements.
Extracted from element_locator.py for better modularity.
"""

import re
import unicodedata
from typing import List, Optional, Tuple
from exceptions import AmbiguousMatchError


def normalize_text(text: str) -> str:
    """Normalize text for comparison by handling special characters and whitespace.
    
    Handles:
    - HTML entities like &nbsp;, &amp;, etc.
    - Accented characters (e.g., â -> a, é -> e) via Unicode normalization
    - Special characters like Â
    - Multiple whitespace
    - Leading/trailing whitespace
    """
    if not text:
        return ""
    
    # Convert to lowercase and strip
    normalized = text.lower().strip()
    
    # Replace HTML entities (common ones)
    normalized = normalized.replace('&nbsp;', ' ')
    normalized = normalized.replace('&amp;', '&')
    normalized = normalized.replace('&lt;', '<')
    normalized = normalized.replace('&gt;', '>')
    normalized = normalized.replace('&quot;', '"')
    normalized = normalized.replace('&#39;', "'")
    
    # Normalize Unicode characters: decompose accented characters and remove diacritics
    # This converts characters like 'â' to 'a', 'é' to 'e', etc.
    normalized = unicodedata.normalize('NFD', normalized)
    # Remove combining marks (diacritics) - these are Unicode characters in the Mn (Mark, Nonspacing) category
    normalized = ''.join(char for char in normalized if unicodedata.category(char) != 'Mn')
    
    # Remove duplicate consecutive letters that may result from normalization
    # (e.g., 'insigniaâ' -> 'insigniaa' -> 'insignia')
    normalized = re.sub(r'([a-z])\1+', r'\1', normalized)
    
    # Remove special characters that aren't word characters, whitespace, or common punctuation
    normalized = re.sub(r'[^\w\s,.-]', '', normalized)
    
    # Normalize whitespace (multiple spaces to single space)
    normalized = re.sub(r'\s+', ' ', normalized)
    
    return normalized.strip()


class LocatorStrategy:
    """Base class for element location strategies."""
    
    ASPECT_RATIO_TOLERANCE = 0.15  # 15% tolerance for aspect ratio matching
    
    def __init__(self, fingerprint: dict, target_element_type: str, target_element_text: str, original_box: Optional[dict] = None):
        self.fingerprint = fingerprint
        self.target_element_type = target_element_type
        self.target_element_text = target_element_text
        self.original_box = original_box
        self.IOU_THRESHOLD = 0.5
    
    async def try_strategy(self, page, description: str, candidates, text: str, has_meaningful_text: bool, filter_text: bool = True):
        """Try a locator strategy with filtering and disambiguation."""
        if not candidates:
            return None
        
        # Filter by text only if meaningful
        if filter_text and has_meaningful_text:
            candidates = await self._filter_by_text(candidates, text)
            if len(candidates) == 1:
                print(f"  ✅ {description}: found 1 element (text-matched)")
                return candidates[0]
        
        # Always filter by type
        candidates = await self._filter_by_type(candidates, self.target_element_type)
        if len(candidates) == 1:
            print(f"  ✅ {description}: found 1 element (type-matched)")
            return candidates[0]
        
        if len(candidates) > 1:
            print(f"  ⚠️ {description}: found {len(candidates)} candidates, disambiguating")
            return await self._disambiguate_candidates(candidates)
        
        return None
    
    async def _filter_by_text(self, candidates, text: str) -> List:
        """Filter candidates by text content with normalization."""
        matched = []
        normalized_target = normalize_text(text)
        
        for candidate in candidates:
            try:
                candidate_text = await candidate.text_content() or ""
                normalized_candidate = normalize_text(candidate_text)
                
                # Check if normalized texts match (substring or contains)
                if normalized_target in normalized_candidate or normalized_candidate in normalized_target:
                    matched.append(candidate)
            except Exception:
                continue
        
        return matched if matched else candidates
    
    async def _filter_by_type(self, candidates, target_type: str) -> List:
        """Filter candidates by element type."""
        matched = []
        type_lower = target_type.lower()
        
        for candidate in candidates:
            try:
                tag_name = (await candidate.evaluate("el => el.tagName.toLowerCase()")).lower()
                
                if type_lower == 'link' and tag_name == 'a':
                    matched.append(candidate)
                elif type_lower == 'button' and tag_name in ('button', 'input') and (await candidate.evaluate("el => el.type")) in ('button', 'submit'):
                    matched.append(candidate)
                elif type_lower in ('input', 'textbox', 'searchbox') and tag_name == 'input':
                    input_type = await candidate.evaluate("el => el.type")
                    if type_lower == 'searchbox' and input_type == 'search':
                        matched.append(candidate)
                    elif type_lower in ('input', 'textbox') and input_type in ('text', 'email', 'password', 'tel', 'url'):
                        matched.append(candidate)
                elif type_lower == 'combobox' and tag_name == 'select':
                    matched.append(candidate)
                elif type_lower == 'checkbox' and tag_name == 'input' and (await candidate.evaluate("el => el.type")) == 'checkbox':
                    matched.append(candidate)
                elif type_lower == 'radio' and tag_name == 'input':
                    input_type = await candidate.evaluate("el => el.type")
                    if input_type != 'radio':
                        continue
                    matched.append(candidate)
            except Exception:
                continue
        
        return matched if matched else candidates
    
    def _calculate_aspect_ratio(self, box: dict) -> Optional[float]:
        """Calculate aspect ratio (width/height) from bounding box."""
        width = box.get('width', 0)
        height = box.get('height', 0)
        if height > 0:
            return width / height
        return None
    
    async def _disambiguate_candidates(self, candidates):
        """Disambiguate candidates using text match, then aspect ratio, then IoU as fallback."""
        if not candidates:
            raise AmbiguousMatchError("No candidates for disambiguation")
        
        # First, try to filter by text if available (most reliable)
        if self.target_element_text and self.target_element_text.strip():
            text_matched = await self._filter_by_text(candidates, self.target_element_text)
            if len(text_matched) == 1:
                print(f"  ✅ Disambiguated by text: 1 match")
                return text_matched[0]
            elif len(text_matched) > 1:
                candidates = text_matched
                print(f"  📝 Filtered to {len(candidates)} text-matched candidates")
        
        # Filter by type if available
        if self.target_element_type:
            type_matched = await self._filter_by_type(candidates, self.target_element_type)
            if len(type_matched) == 1:
                print(f"  ✅ Disambiguated by type match")
                return type_matched[0]
            elif len(type_matched) > 1:
                candidates = type_matched
                print(f"  📝 Filtered to {len(candidates)} type-matched candidates")
        
        # Use aspect ratio matching if we have bounding box (preferred over IoU)
        if self.original_box:
            aspect_ratio_result = await self._disambiguate_with_aspect_ratio(candidates)
            if aspect_ratio_result:
                return aspect_ratio_result
            # Fallback to IoU if aspect ratio doesn't work
            return await self._disambiguate_with_iou(candidates)
        
        # If no bounding box, raise error
        raise AmbiguousMatchError(f"Found {len(candidates)} candidates, cannot disambiguate without bounding box")
    
    async def _disambiguate_with_aspect_ratio(self, candidates):
        """Use aspect ratio matching to pick the best candidate."""
        if not candidates or not self.original_box:
            return None
        
        orig_aspect = self._calculate_aspect_ratio(self.original_box)
        if orig_aspect is None:
            return None
        
        candidate_data = []
        for candidate in candidates:
            if box := await candidate.bounding_box():
                candidate_aspect = self._calculate_aspect_ratio(box)
                if candidate_aspect is not None:
                    # Calculate relative difference
                    aspect_diff = abs(candidate_aspect - orig_aspect) / orig_aspect
                    area = box.get('width', 0) * box.get('height', 0)
                    candidate_data.append({
                        'element': candidate,
                        'aspect_ratio': candidate_aspect,
                        'aspect_diff': aspect_diff,
                        'area': area
                    })
        
        if not candidate_data:
            return None
        
        # Filter candidates within tolerance
        within_tolerance = [
            c for c in candidate_data
            if c['aspect_diff'] <= self.ASPECT_RATIO_TOLERANCE
        ]
        
        if len(within_tolerance) == 1:
            print(f"  ✅ Disambiguated by aspect ratio: {within_tolerance[0]['aspect_ratio']:.2f} (diff={within_tolerance[0]['aspect_diff']:.3f})")
            return within_tolerance[0]['element']
        elif len(within_tolerance) > 1:
            # Multiple candidates within tolerance, pick closest aspect ratio
            within_tolerance.sort(key=lambda x: x['aspect_diff'])
            best = within_tolerance[0]
            print(f"  ✅ Disambiguated by aspect ratio: {best['aspect_ratio']:.2f} (diff={best['aspect_diff']:.3f}, {len(within_tolerance)} within tolerance)")
            return best['element']
        else:
            # No candidates within tolerance, but return best match anyway
            candidate_data.sort(key=lambda x: x['aspect_diff'])
            best = candidate_data[0]
            print(f"  ⚠️ No candidates within aspect ratio tolerance, using best match: {best['aspect_ratio']:.2f} (diff={best['aspect_diff']:.3f})")
            # Only return if difference is reasonable (less than 50%)
            if best['aspect_diff'] < 0.5:
                return best['element']
        
        return None
    
    async def _disambiguate_with_iou(self, candidates):
        """Use IoU as fallback when aspect ratio matching fails."""
        if not candidates or not self.original_box:
            raise AmbiguousMatchError("No candidates or bounding box for disambiguation")
        
        orig = self.original_box
        orig_area = orig['width'] * orig['height']
        
        candidate_data = []
        for candidate in candidates:
            if box := await candidate.bounding_box():
                iou = self._calculate_iou(orig, box)
                area_diff = abs(box.get('width', 0) * box.get('height', 0) - orig_area)
                
                candidate_data.append({
                    'element': candidate, 'iou': iou, 'area_diff': area_diff
                })
        
        if not candidate_data:
            raise AmbiguousMatchError(f"Found {len(candidates)} candidates but none had valid bounding boxes")
        
        # Sort by IoU, then by area difference
        candidate_data.sort(key=lambda x: (-x['iou'], x['area_diff']))
        best = candidate_data[0]
        
        print(f"  ⚠️ Using IoU fallback: IoU={best['iou']:.2f}, area_diff={best['area_diff']:.1f}")
        return best['element']
    
    def _calculate_iou(self, box1: dict, box2: dict) -> float:
        """Calculate Intersection over Union (IoU) of two bounding boxes."""
        x1 = max(box1.get('x', 0), box2.get('x', 0))
        y1 = max(box1.get('y', 0), box2.get('y', 0))
        x2 = min(box1.get('x', 0) + box1.get('width', 0), box2.get('x', 0) + box2.get('width', 0))
        y2 = min(box1.get('y', 0) + box1.get('height', 0), box2.get('y', 0) + box2.get('height', 0))
        
        if x2 <= x1 or y2 <= y1:
            return 0.0
        
        intersection = (x2 - x1) * (y2 - y1)
        area1 = box1.get('width', 0) * box1.get('height', 0)
        area2 = box2.get('width', 0) * box2.get('height', 0)
        union = area1 + area2 - intersection
        
        return intersection / union if union > 0 else 0.0
    
    async def execute(self, page) -> Optional:
        """Execute this strategy. Must be implemented by subclasses."""
        raise NotImplementedError


class IdStrategy(LocatorStrategy):
    """Strategy 1: ID (most specific - IDs are unique)."""
    
    async def execute(self, page) -> Optional:
        if 'id' not in self.fingerprint:
            return None
        
        candidates = await page.locator(f"#{self.fingerprint['id']}").all()
        if len(candidates) == 1:
            print(f"  ✅ ID: found 1 element (unique)")
            return candidates[0]
        elif candidates:
            text = self.target_element_text.strip()
            has_meaningful_text = text and text.strip()
            return await self.try_strategy(page, "ID", candidates, text, has_meaningful_text, filter_text=False)
        return None


class DataTestIdStrategy(LocatorStrategy):
    """Strategy 2: data-testid (very specific)."""
    
    async def execute(self, page) -> Optional:
        if 'data_testid' not in self.fingerprint:
            return None
        
        test_id = self.fingerprint['data_testid']
        
        # Try multiple data-testid attribute variations
        candidates = await page.locator(f"[data-testid='{test_id}']").all()
        if not candidates:
            candidates = await page.locator(f"[data-pw-testid-buckeye-candidate='{test_id}']").all()
        if not candidates:
            # Also check data-pw-testid-buckeye (without -candidate suffix)
            candidates = await page.locator(f"[data-pw-testid-buckeye='{test_id}']").all()
        if not candidates:
            # Try with attribute containing the test_id (for cases where value is different)
            candidates = await page.locator(f"[data-pw-testid-buckeye*='{test_id}']").all()
        
        if candidates:
            text = self.target_element_text.strip()
            has_meaningful_text = text and text.strip()
            return await self.try_strategy(page, "data-testid", candidates, text, has_meaningful_text, filter_text=False)
        return None


class RoleAndTextStrategy(LocatorStrategy):
    """Strategy 3: Role + text (only if we have meaningful text)."""
    
    async def execute(self, page, role: str) -> Optional:
        text = self.target_element_text.strip()
        has_meaningful_text = text and text.strip()
        
        if not role or not has_meaningful_text:
            return None
        
        candidates = await page.get_by_role(role, name=text, exact=False).all()
        if candidates:
            return await self.try_strategy(page, f"role={role}+text", candidates, text, has_meaningful_text)
        return None


class TextStrategy(LocatorStrategy):
    """Strategy 4: Text search (only if meaningful text)."""
    
    async def execute(self, page) -> Optional:
        text = self.target_element_text.strip()
        has_meaningful_text = text and text.strip()
        
        if not has_meaningful_text:
            return None
        
        candidates = await page.get_by_text(text, exact=False).all()
        if candidates:
            return await self.try_strategy(page, "text", candidates, text, has_meaningful_text)
        return None


class FingerprintStrategy(LocatorStrategy):
    """Strategy 5: Fingerprint-based (aria-label, role, placeholder, name)."""
    
    async def execute(self, page, type_lower: str) -> Optional:
        text = self.target_element_text.strip()
        has_meaningful_text = text and text.strip()
        
        if 'aria_label' in self.fingerprint:
            candidates = await page.get_by_label(self.fingerprint['aria_label']).all()
            result = await self.try_strategy(page, "aria-label", candidates, text, has_meaningful_text)
            if result:
                return result
        
        if 'role' in self.fingerprint:
            candidates = await page.get_by_role(self.fingerprint['role']).all()
            result = await self.try_strategy(page, "role", candidates, text, has_meaningful_text)
            if result:
                return result
        
        if 'placeholder' in self.fingerprint and type_lower in ('input', 'searchbox'):
            candidates = await page.get_by_placeholder(self.fingerprint['placeholder']).all()
            result = await self.try_strategy(page, "placeholder", candidates, text, has_meaningful_text)
            if result:
                return result
        
        if 'name' in self.fingerprint:
            candidates = await page.locator(f"[name='{self.fingerprint['name']}']").all()
            result = await self.try_strategy(page, "name", candidates, text, has_meaningful_text)
            if result:
                return result
        
        return None


class TagAndClassStrategy(LocatorStrategy):
    """Strategy 6: Tag + class (less specific)."""
    
    async def execute(self, page, type_lower: str) -> Optional:
        text = self.target_element_text.strip()
        has_meaningful_text = text and text.strip()
        
        tag = self.fingerprint.get('tag', type_lower)
        class_name = self.fingerprint.get('class')
        
        if class_name:
            candidates = await page.locator(f"{tag}.{class_name.replace(' ', '.')}").all()
            if not candidates:
                candidates = await page.locator(f"{tag}[class*='{class_name.split()[0]}']").all()
        else:
            candidates = await page.locator(tag).all()
        
        if candidates:
            return await self.try_strategy(page, f"tag={tag}+class", candidates, text, has_meaningful_text)
        return None


class BroadSearchStrategy(LocatorStrategy):
    """Strategy 7: Broad search (last resort)."""
    
    async def execute(self, page) -> Optional:
        text = self.target_element_text.strip()
        has_meaningful_text = text and text.strip()
        
        if not has_meaningful_text:
            return None
        
        candidates = await page.locator(f"text={text}").all()
        if candidates:
            return await self.try_strategy(page, "broad search", candidates, text, has_meaningful_text)
        return None


class ContextualContainerStrategy(LocatorStrategy):
    """Strategy 8: Contextual matching using parent container text (for multiple identical elements)."""
    
    async def execute(self, page, type_lower: str) -> Optional:
        """Find element by locating parent container with descriptive text, then target within container."""
        text = self.target_element_text.strip()
        has_meaningful_text = text and text.strip()
        
        if not has_meaningful_text:
            return None
        
        # Try to extract descriptive text and target text
        descriptive_text, target_text = self._extract_descriptive_and_target_text(text)
        
        if not descriptive_text or not target_text:
            return None
        
        # Find all elements matching target text
        target_candidates = await page.get_by_text(target_text, exact=False).all()
        
        if not target_candidates:
            return None
        
        # Fix: If get_by_text returns child elements (like span), find their parent link/button elements
        target_candidates = await self._ensure_target_type_elements(target_candidates, type_lower)
        
        if not target_candidates:
            return None
        
        # Filter by type (double-check)
        type_matched = await self._filter_by_type(target_candidates, self.target_element_type)
        
        if not type_matched:
            return None
        
        # Filter candidates that are within containers containing descriptive text
        contextual_candidates = []
        for candidate in type_matched:
            if await self._is_in_container_with_text(candidate, descriptive_text):
                contextual_candidates.append(candidate)
        
        if len(contextual_candidates) == 1:
            print(f"  ✅ Contextual: found 1 element in container with '{descriptive_text}'")
            return contextual_candidates[0]
        elif len(contextual_candidates) > 1:
            print(f"  ⚠️ Contextual: found {len(contextual_candidates)} candidates in containers, disambiguating")
            return await self._disambiguate_candidates(contextual_candidates)
        
        return None
    
    async def _ensure_target_type_elements(self, candidates, type_lower: str) -> List:
        """Ensure candidates are of the target type. If not, find parent elements of the correct type.
        
        For example, if get_by_text returns a <span> but we need a <a> (link),
        traverse up to find the parent <a> element.
        """
        result = []
        target_tags = {
            'link': ['a'],
            'button': ['button', 'input'],
            'input': ['input'],
            'textbox': ['input'],
            'searchbox': ['input'],
            'combobox': ['select'],
            'checkbox': ['input'],
            'radio': ['input'],
        }
        expected_tags = target_tags.get(type_lower, [])
        
        for candidate in candidates:
            try:
                tag_name = (await candidate.evaluate("el => el.tagName.toLowerCase()")).lower()
                
                # If candidate is already the right type, use it
                if tag_name in expected_tags:
                    result.append(candidate)
                else:
                    # Traverse up to find parent element of correct type
                    parent = await self._find_parent_of_type(candidate, expected_tags)
                    if parent and parent not in result:
                        result.append(parent)
            except Exception:
                continue
        
        return result
    
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
    
    def _extract_descriptive_and_target_text(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract descriptive text and target text from combined text.
        
        Example: "Opel Insignia or Similar , View deal" -> 
        descriptive: "Opel Insignia or Similar", target: "View deal"
        """
        # Split by common separators
        parts = [p.strip() for p in text.split(',')]
        
        if len(parts) < 2:
            return None, None
        
        # Last part is usually the target (button/link text)
        target_text = parts[-1].strip()
        
        # Everything before last comma is descriptive
        descriptive_text = ', '.join(parts[:-1]).strip()
        
        # Only proceed if both are meaningful (at least 3 chars)
        if len(descriptive_text) >= 3 and len(target_text) >= 3:
            return descriptive_text, target_text
        
        return None, None
    
    async def _is_in_container_with_text(self, element, descriptive_text: str) -> bool:
        """Check if element is within a container that contains the descriptive text.
        
        Uses normalized text comparison to handle special characters.
        """
        try:
            # Normalize the descriptive text for comparison
            normalized_desc = normalize_text(descriptive_text)
            
            # Traverse up the DOM tree from the element to find if any parent contains the descriptive text
            result = await element.evaluate("""
                (el, normalizedDescText) => {
                    let current = el;
                    let depth = 0;
                    const maxDepth = 15;
                    
                    // Simple normalization function (matches Python normalize_text logic)
                    function normalizeText(text) {
                        if (!text) return "";
                        let normalized = text.toLowerCase().trim();
                        normalized = normalized.replace(/&nbsp;/g, ' ');
                        normalized = normalized.replace(/&amp;/g, '&');
                        normalized = normalized.replace(/[^\\w\\s,.-]/g, '');
                        normalized = normalized.replace(/\\s+/g, ' ');
                        return normalized.trim();
                    }
                    
                    while (current && depth < maxDepth) {
                        // Check if current element contains the descriptive text
                        const containerText = current.textContent || '';
                        const normalizedContainerText = normalizeText(containerText);
                        
                        if (normalizedContainerText.includes(normalizedDescText) || 
                            normalizedDescText.includes(normalizedContainerText)) {
                            // Check if this is a reasonable container
                            const tagName = current.tagName.toLowerCase();
                            if (['div', 'section', 'article', 'li', 'tr', 'td', 'body', 'a'].includes(tagName)) {
                                return true;
                            }
                        }
                        
                        current = current.parentElement;
                        if (!current || current.tagName === 'HTML') break;
                        depth++;
                    }
                    
                    return false;
                }
            """, normalized_desc)
            
            return result
        except Exception:
            return False

