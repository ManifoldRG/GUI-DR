"""
Locator Strategies - Individual strategy classes for finding elements.
Extracted from element_locator.py for better modularity.
"""

from typing import List, Optional
from exceptions import AmbiguousMatchError


class LocatorStrategy:
    """Base class for element location strategies."""
    
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
            return await self._disambiguate_with_text_and_iou(candidates)
        
        return None
    
    async def _filter_by_text(self, candidates, text: str) -> List:
        """Filter candidates by text content."""
        matched = []
        text_lower = text.lower().strip()
        
        for candidate in candidates:
            try:
                candidate_text = (await candidate.text_content() or "").strip().lower()
                if text_lower in candidate_text or candidate_text in text_lower:
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
    
    async def _disambiguate_with_text_and_iou(self, candidates):
        """Disambiguate candidates using text match first, then IoU."""
        if not candidates:
            raise AmbiguousMatchError("No candidates for disambiguation")
        
        # First, try to filter by text if available (most reliable)
        if self.target_element_text:
            text_matched = await self._filter_by_text(candidates, self.target_element_text)
            if len(text_matched) == 1:
                print(f"  ✅ Disambiguated by text: 1 match")
                return text_matched[0]
            elif len(text_matched) > 1:
                candidates = text_matched
        
        # If we have original bounding box, use IoU
        if self.original_box:
            return await self._disambiguate_with_iou(candidates)
        
        # No disambiguation possible
        raise AmbiguousMatchError(f"Found {len(candidates)} candidates, cannot disambiguate without bounding box")
    
    async def _disambiguate_with_iou(self, candidates):
        """Use IoU and area matching to pick the best candidate."""
        if not candidates or not self.original_box:
            raise AmbiguousMatchError("No candidates or bounding box for disambiguation")
        
        orig = self.original_box
        orig_area = orig['width'] * orig['height']
        orig_center = (orig['x'] + orig['width'] / 2, orig['y'] + orig['height'] / 2)
        
        candidate_data = []
        for candidate in candidates:
            if box := await candidate.bounding_box():
                iou = self._calculate_iou(orig, box)
                area_diff = abs(box.get('width', 0) * box.get('height', 0) - orig_area)
                cx, cy = box.get('x', 0) + box.get('width', 0) / 2, box.get('y', 0) + box.get('height', 0) / 2
                center_dist = ((cx - orig_center[0]) ** 2 + (cy - orig_center[1]) ** 2) ** 0.5
                
                candidate_data.append({
                    'element': candidate, 'iou': iou, 'area_diff': area_diff, 'center_distance': center_dist
                })
        
        if not candidate_data:
            raise AmbiguousMatchError(f"Found {len(candidates)} candidates but none had valid bounding boxes")
        
        candidate_data.sort(key=lambda x: (-x['iou'], x['area_diff']))
        best = candidate_data[0]
        
        if best['iou'] < 0.1:
            print(f"  ⚠️ Low IoU ({best['iou']:.2f}), falling back to center distance matching")
            candidate_data.sort(key=lambda x: (x['center_distance'], x['area_diff']))
            best = candidate_data[0]
        
        if best['iou'] < self.IOU_THRESHOLD and best['center_distance'] > 100:
            print(f"  ⚠️ Low confidence match: IoU={best['iou']:.2f}, distance={best['center_distance']:.1f}")
        
        print(f"  ✅ Disambiguated by IoU: best match (IoU={best['iou']:.2f})")
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
        
        candidates = await page.locator(f"[data-testid='{self.fingerprint['data_testid']}']").all()
        if not candidates:
            candidates = await page.locator(f"[data-pw-testid-buckeye-candidate='{self.fingerprint['data_testid']}']").all()
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

