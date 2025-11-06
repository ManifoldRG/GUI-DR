"""
Element Locator - Finds elements using a priority cascade strategy.
Simplified to use strategy classes.
"""

import json
from typing import Dict, Optional, List

from exceptions import ElementLocatorError, ElementNotFoundError, AmbiguousMatchError
from locator_strategies import (
    IdStrategy, DataTestIdStrategy, RoleAndTextStrategy, TextStrategy,
    FingerprintStrategy, TagAndClassStrategy, BroadSearchStrategy
)


class ElementLocator:
    """
    Finds elements using a simple priority cascade strategy.
    Tries each locator method in order, stops at first success.
    """
    
    IOU_THRESHOLD = 0.5  # Minimum IoU for spatial disambiguation

    def __init__(self, pos_candidate_json: str, target_element_type: str, target_element_text: str):
        """Parses the input JSON and extracts fingerprint + bounding box."""
        try:
            parsed_data = json.loads(pos_candidate_json) if isinstance(pos_candidate_json, str) else pos_candidate_json
        except json.JSONDecodeError:
            raise ValueError("Input is not valid JSON.")
        
        try:
            attrs_str = parsed_data.get('attributes', '{}')
            self.attrs = json.loads(attrs_str) if isinstance(attrs_str, str) else attrs_str or {}
        except json.JSONDecodeError:
            self.attrs = {}
        
        self.parsed_data = parsed_data
        self.fingerprint: Dict[str, str] = {}
        self._extract_fingerprint()
        self.original_box = self._extract_bbox()
        self.target_element_type = target_element_type
        self.target_element_text = target_element_text

    def _get_attr(self, key: str, normalize: bool = True) -> Optional[str]:
        """Get attribute value from nested or top-level, optionally normalize key."""
        value = self.attrs.get(key) or self.attrs.get(key.replace('_', '-'))
        if not value:
            value = self.parsed_data.get(key)
        if value and str(value).strip():
            return str(value).strip()
        return None
    
    def _extract_fingerprint(self):
        """Extract element fingerprint from attributes."""
        if tag := self.parsed_data.get('tag'):
            self.fingerprint['tag'] = tag
        
        for key in ['id', 'aria_label', 'aria-label', 'placeholder', 'name']:
            if value := self._get_attr(key):
                self.fingerprint[key.replace('-', '_')] = value
        
        if value := self._get_attr('role'):
            self.fingerprint['role'] = value
        
        if value := self._get_attr('class'):
            classes = value.split()
            if classes:
                self.fingerprint['class'] = classes[0]
        
        test_id = (self.attrs.get('data-testid') or 
                  self.attrs.get('data_pw_testid_buckeye_candidate') or
                  self.attrs.get('data-testid_buckeye_candidate'))
        if test_id and str(test_id).strip():
            self.fingerprint['data_testid'] = str(test_id).strip()
    
    def _extract_bbox(self) -> Optional[Dict[str, float]]:
        """Extract bounding box from attributes."""
        bbox_str = self.attrs.get('bounding_box_rect') or self.parsed_data.get('bounding_box_rect')
        if not bbox_str or not isinstance(bbox_str, str):
            return None
        
        try:
            parts = bbox_str.split(',')
            if len(parts) >= 4:
                return {
                    'x': float(parts[0]),
                    'y': float(parts[1]),
                    'width': float(parts[2]),
                    'height': float(parts[3])
                }
        except (ValueError, IndexError):
            pass
        return None

    
    async def find_element(self, page):
        """Find element using text, type, and fingerprint in priority order.
        Assumes target_element_text and target_element_type are always available."""
        if not self.target_element_text or not self.target_element_type:
            raise ElementNotFoundError("target_element_text and target_element_type must be provided")
        
        print(f"🔍 Searching for element: type='{self.target_element_type}', text='{self.target_element_text}'")
        print(f"   Fingerprint: {self.fingerprint}")
        
        type_lower = self.target_element_type.lower()
        
        # Map type to Playwright role
        type_to_role = {
            'link': 'link', 'button': 'button', 'searchbox': 'searchbox',
            'input': 'textbox', 'textbox': 'textbox', 'combobox': 'combobox',
            'checkbox': 'checkbox', 'menuitem': 'menuitem', 'heading': 'heading', 'option': 'option',
        }
        role = type_to_role.get(type_lower)
        
        # Create strategy instances
        strategies = [
            IdStrategy(self.fingerprint, self.target_element_type, self.target_element_text, self.original_box),
            DataTestIdStrategy(self.fingerprint, self.target_element_type, self.target_element_text, self.original_box),
            RoleAndTextStrategy(self.fingerprint, self.target_element_type, self.target_element_text, self.original_box),
            TextStrategy(self.fingerprint, self.target_element_type, self.target_element_text, self.original_box),
            FingerprintStrategy(self.fingerprint, self.target_element_type, self.target_element_text, self.original_box),
            TagAndClassStrategy(self.fingerprint, self.target_element_type, self.target_element_text, self.original_box),
            BroadSearchStrategy(self.fingerprint, self.target_element_type, self.target_element_text, self.original_box),
        ]
        
        # Try strategies in priority order
        for strategy in strategies:
            if isinstance(strategy, RoleAndTextStrategy):
                result = await strategy.execute(page, role)
            elif isinstance(strategy, (FingerprintStrategy, TagAndClassStrategy)):
                result = await strategy.execute(page, type_lower)
            else:
                result = await strategy.execute(page)
            
            if result:
                return result
        
        raise ElementNotFoundError(
            f"No element found: type='{self.target_element_type}', text='{self.target_element_text}', "
            f"fingerprint={self.fingerprint}"
        )

    async def _disambiguate_with_text_and_iou(self, candidates):
        """Disambiguate candidates using text match first, then IoU."""
        if not candidates:
            raise AmbiguousMatchError("No candidates for disambiguation")
        
        # First, try to filter by text if available (most reliable)
        if self.target_element_text:
            text_matched = await self._filter_by_text(candidates, self.target_element_text)
            if len(text_matched) == 1:
                print(f"  ✅ Disambiguated by text match")
                return text_matched[0]
            elif len(text_matched) > 1:
                # Use text-matched candidates for IoU disambiguation
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
        
        # Use IoU for spatial disambiguation if we have bounding box and multiple candidates
        if self.original_box and len(candidates) > 1:
            return await self._disambiguate_with_iou(candidates)
        
        # If no bounding box or only one candidate, return first candidate
        if len(candidates) == 1:
            return candidates[0]
        
        # Fallback: return first candidate (shouldn't happen often)
        print(f"  ⚠️ No bounding box for IoU, returning first candidate")
        return candidates[0]

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
            raise AmbiguousMatchError(
                f"Found {len(candidates)} candidates but best match has IoU {best['iou']:.2f} "
                f"and center distance {best['center_distance']:.1f}px"
            )
        
        print(f"  ✅ Selected: IoU={best['iou']:.2f}, center_dist={best['center_distance']:.1f}px")
        return best['element']

    def _calculate_iou(self, box1: Dict, box2: Dict) -> float:
        """Calculate Intersection over Union between two bounding boxes."""
        try:
            x1, y1, w1, h1 = box1.get('x', 0), box1.get('y', 0), box1.get('width', 0), box1.get('height', 0)
            x2, y2, w2, h2 = box2.get('x', 0), box2.get('y', 0), box2.get('width', 0), box2.get('height', 0)
            
            x_left, y_top = max(x1, x2), max(y1, y2)
            x_right, y_bottom = min(x1 + w1, x2 + w2), min(y1 + h1, y2 + h2)
            
            if x_right <= x_left or y_bottom <= y_top:
                return 0.0
            
            intersection = (x_right - x_left) * (y_bottom - y_top)
            union = w1 * h1 + w2 * h2 - intersection
            return intersection / union if union > 0 else 0.0
        except Exception:
            return 0.0

