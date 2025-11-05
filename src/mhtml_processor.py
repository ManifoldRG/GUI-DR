"""
MHTML Processor - Minimal Prototype

Processes MHTML files, injects UI modifications, and extracts element coordinates.
"""

import asyncio
import json
import os
import random
import traceback
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass
from PIL import Image
from randomization import generate_diverse_ui_params
from ui_injection import generate_injection_js


@dataclass
class ActionEntry:
    """Single action entry with UUID and target element info"""
    action_uid: str
    op: str
    pos_element: List[str]
    confirmed_task: str = ""  # Mock value placeholder


class ElementLocatorError(Exception):
    """Base exception for element location failures"""
    pass


class ElementNotFoundError(ElementLocatorError):
    """No element found matching fingerprint"""
    pass


class AmbiguousMatchError(ElementLocatorError):
    """Multiple elements found, cannot disambiguate"""
    pass


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
        if self.parsed_data.get('tag'):
            self.fingerprint['tag'] = self.parsed_data['tag']
        
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

    async def _filter_by_text(self, candidates, target_text: str) -> List:
        """Filter candidates by matching text content, placeholder, or label."""
        if not target_text or not candidates:
            return candidates
        
        target_text_lower = target_text.lower().strip()
        # If text is empty or just whitespace, don't filter by text
        if not target_text_lower:
            return candidates
        
        matched = []
        
        for candidate in candidates:
            try:
                # For input elements, check placeholder and associated label
                tag_name = await candidate.evaluate("el => el.tagName.toLowerCase()")
                if tag_name == 'input':
                    # Check placeholder
                    placeholder = await candidate.get_attribute('placeholder')
                    if placeholder and target_text_lower in placeholder.lower():
                        matched.append(candidate)
                        continue
                    
                    # Check associated label
                    input_id = await candidate.get_attribute('id')
                    if input_id:
                        label_text = await candidate.evaluate(f"""
                            () => {{
                                const label = document.querySelector(`label[for='{input_id}']`);
                                return label ? label.textContent : null;
                            }}
                        """)
                        if label_text and target_text_lower in label_text.lower():
                            matched.append(candidate)
                            continue
                
                # For other elements, check text content
                text = await candidate.text_content()
                if text and target_text_lower in text.lower():
                    matched.append(candidate)
            except Exception:
                continue
        
        return matched if matched else candidates  # Return original if no matches

    async def _filter_by_type(self, candidates, target_type: str) -> List:
        """Filter candidates by element type. Type can be a tag name or role."""
        if not target_type or not candidates:
            return candidates
        
        target_type_lower = target_type.lower()
        
        # Standard HTML tags
        html_tags = {'button', 'div', 'span', 'p', 'a', 'li', 'input', 'textarea', 
                    'select', 'option', 'svg', 'img', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                    'ul', 'ol', 'table', 'tr', 'td', 'th', 'form', 'label', 'header', 
                    'footer', 'nav', 'section', 'article', 'aside'}
        
        # Map common role names to HTML tags
        role_to_tag = {
            'link': 'a',
            'searchbox': 'input',
            'input': 'input',
            'textbox': 'input',
            'checkbox': 'input',  # checkbox is input[type="checkbox"]
        }
        
        # Try role-to-tag mapping first, then use type directly as tag name
        expected_tag = role_to_tag.get(target_type_lower)
        if not expected_tag and target_type_lower in html_tags:
            expected_tag = target_type_lower
        
        if not expected_tag:
            return candidates
        
        matched = []
        for candidate in candidates:
            try:
                # Check tag name
                tag_name = await candidate.evaluate("el => el.tagName.toLowerCase()")
                if tag_name != expected_tag:
                    continue
                
                # For checkbox/radio, also verify the input type
                if target_type_lower == 'checkbox' and tag_name == 'input':
                    input_type = await candidate.evaluate("el => el.type")
                    if input_type != 'checkbox':
                        continue
                elif target_type_lower == 'radio' and tag_name == 'input':
                    input_type = await candidate.evaluate("el => el.type")
                    if input_type != 'radio':
                        continue
                
                matched.append(candidate)
            except Exception:
                continue
        
        return matched if matched else candidates

    async def find_element(self, page):
        """Find element using text, type, and fingerprint in priority order.
        Assumes target_element_text and target_element_type are always available."""
        if not self.target_element_text or not self.target_element_type:
            raise ValueError("target_element_text and target_element_type must be provided")
        
        print(f"🔍 Searching for element: type='{self.target_element_type}', text='{self.target_element_text}'")
        print(f"   Fingerprint: {self.fingerprint}")
        
        text = self.target_element_text.strip()
        type_lower = self.target_element_type.lower()
        has_meaningful_text = bool(text and text.strip())
        
        async def try_strategy(description, candidates, filter_text=True):
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
            
            if len(candidates) == 1:
                print(f"  ✅ {description}: found 1 element")
                return candidates[0]
            
            if len(candidates) > 1:
                print(f"  ⚠️ {description}: found {len(candidates)} candidates, disambiguating")
                return await self._disambiguate_with_text_and_iou(candidates)
            
            return None
        
        # Map type to Playwright role
        type_to_role = {
            'link': 'link', 'button': 'button', 'searchbox': 'searchbox',
            'input': 'textbox', 'textbox': 'textbox', 'combobox': 'combobox',
            'checkbox': 'checkbox', 'menuitem': 'menuitem', 'heading': 'heading', 'option': 'option',
        }
        role = type_to_role.get(type_lower)
        
        # Strategy 1: ID (most specific - IDs are unique, so if found, return immediately)
        if 'id' in self.fingerprint:
            candidates = await page.locator(f"#{self.fingerprint['id']}").all()
            if len(candidates) == 1:
                # ID is unique, so if we found exactly one, it's the right element
                print(f"  ✅ ID: found 1 element (unique)")
                return candidates[0]
            elif candidates:
                # Multiple candidates with same ID shouldn't happen, but handle it
                result = await try_strategy("ID", candidates, filter_text=False)
                if result:
                    return result
        
        # Strategy 2: data-testid (very specific, prioritize when text is not meaningful)
        if 'data_testid' in self.fingerprint:
            candidates = await page.locator(f"[data-testid='{self.fingerprint['data_testid']}']").all()
            if not candidates:
                candidates = await page.locator(f"[data-pw-testid-buckeye-candidate='{self.fingerprint['data_testid']}']").all()
            if candidates:
                result = await try_strategy("data-testid", candidates, filter_text=False)
                if result:
                    return result
        
        # Strategy 3: Role + text (only if we have meaningful text)
        if role and has_meaningful_text:
            candidates = await page.get_by_role(role, name=text, exact=False).all()
            if candidates:
                result = await try_strategy(f"role={role}+text", candidates)
                if result:
                    return result
        
        # Strategy 4: Text search (only if meaningful text)
        if has_meaningful_text:
            candidates = await page.get_by_text(text, exact=False).all()
            if candidates:
                result = await try_strategy("text", candidates)
                if result:
                    return result
        
        # Strategy 5: Fingerprint-based (aria-label, role, etc.)
        if 'aria_label' in self.fingerprint:
            candidates = await page.get_by_label(self.fingerprint['aria_label']).all()
            result = await try_strategy("aria-label", candidates)
            if result:
                return result
        
        if 'role' in self.fingerprint:
            candidates = await page.get_by_role(self.fingerprint['role']).all()
            result = await try_strategy("role", candidates)
            if result:
                return result
        
        if 'placeholder' in self.fingerprint and type_lower in ('input', 'searchbox'):
            candidates = await page.get_by_placeholder(self.fingerprint['placeholder']).all()
            result = await try_strategy("placeholder", candidates)
            if result:
                return result
        
        if 'name' in self.fingerprint:
            candidates = await page.locator(f"[name='{self.fingerprint['name']}']").all()
            result = await try_strategy("name", candidates)
            if result:
                return result
        
        # Use fingerprint tag+class to find parent, then find target type inside if different
        if 'tag' in self.fingerprint and 'class' in self.fingerprint:
            fingerprint_tag = self.fingerprint['tag'].lower()
            
            # If fingerprint is label and target might be checkbox/radio, find input first
            if fingerprint_tag == 'label' and type_lower in ('checkbox', 'radio', 'span'):
                # Try to find input checkbox/radio associated with this label
                label_candidates = await page.locator(f"{self.fingerprint['tag']}.{self.fingerprint['class']}").all()
                for label in label_candidates:
                    # Check if label has 'for' attribute
                    label_for = await label.get_attribute('for')
                    if label_for:
                        input_element = page.locator(f"#{label_for}")
                        if await input_element.count() > 0:
                            input_bbox = await input_element.bounding_box()
                            if input_bbox:
                                result = await try_strategy(f"label->input[{label_for}]", [input_element], filter_text=False)
                                if result:
                                    return result
                    else:
                        # Find input inside label
                        input_inside = label.locator("input[type='checkbox'], input[type='radio']")
                        if await input_inside.count() > 0:
                            result = await try_strategy(f"label->input", await input_inside.all(), filter_text=False)
                            if result:
                                return result
            
            # Try the exact tag+class match first
            candidates = await page.locator(f"{self.fingerprint['tag']}.{self.fingerprint['class']}").all()
            result = await try_strategy("tag+class", candidates)
            if result:
                return result
            
            # If target type is different from fingerprint tag (e.g., span inside label), 
            # try finding the target type within the fingerprint element
            if type_lower != fingerprint_tag:
                parent_candidates = await page.locator(f"{self.fingerprint['tag']}.{self.fingerprint['class']}").all()
                for parent in parent_candidates:
                    # Find target type element inside parent
                    inner_candidates = await parent.locator(type_lower).all()
                    if inner_candidates:
                        result = await try_strategy(f"tag+class->{type_lower}", inner_candidates, filter_text=False)
                        if result:
                            return result
        
        # Last resort: broad searches
        if 'class' in self.fingerprint:
            candidates = await page.locator(f".{self.fingerprint['class']}").all()
            result = await try_strategy("class", candidates)
            if result:
                return result
        
        if 'tag' in self.fingerprint:
            candidates = await page.locator(self.fingerprint['tag']).all()
            result = await try_strategy("tag", candidates)
            if result:
                return result
        
        raise ElementNotFoundError(
            f"No element found: type='{self.target_element_type}', text='{self.target_element_text}', "
            f"fingerprint={self.fingerprint}"
        )
    
    async def _diagnose_id_not_found(self, page):
        """Diagnostic helper for when ID is not found."""
        elem_id = self.fingerprint['id']
        exists = await page.evaluate(f"document.getElementById('{elem_id}') !== null")
        if exists:
            info = await page.evaluate(f"""
                () => {{
                    const el = document.getElementById('{elem_id}');
                    if (!el) return null;
                    const s = window.getComputedStyle(el);
                    return {{
                        tag: el.tagName.toLowerCase(),
                        visible: s.display !== 'none' && s.visibility !== 'hidden',
                        display: s.display,
                        inViewport: el.getBoundingClientRect().width > 0
                    }};
                }}
            """)
            if info:
                print(f"  ⚠️ ID='{elem_id}': exists but locator found 0 (hidden/in iframe)")
                print(f"  ℹ️ tag={info['tag']}, visible={info['visible']}, display={info['display']}")
        else:
            print(f"  ⚠️ ID='{elem_id}': not found in DOM")
            if 'name' in self.fingerprint:
                count = await page.locator(f"[name='{self.fingerprint['name']}']").count()
                print(f"  ℹ️ Found {count} elements with name='{self.fingerprint['name']}'")
    
    async def _diagnose_inputs(self, page):
        """Diagnostic helper for input elements."""
        diag = await page.evaluate("""
            () => Array.from(document.querySelectorAll('input')).slice(0, 5).map(el => ({
                id: el.id || null,
                name: el.name || null,
                type: el.type || 'text',
                visible: el.offsetParent !== null
            }))
        """)
        print(f"  🔍 Diagnostic: Sample inputs on page:")
        for inp in diag:
            print(f"    - id={inp['id']}, name={inp['name']}, type={inp['type']}, visible={inp['visible']}")

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
        
        # Use IoU for spatial disambiguation if we have bounding box
        if self.original_box and len(candidates) > 1:
            return await self._disambiguate_with_iou(candidates)
        elif len(candidates) == 1:
            return candidates[0]
        else:
            # If no bounding box, return first candidate (shouldn't happen often)
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


class MHTMLProcessor:
    """Minimal MHTML processor with UI modification support"""
    
    def __init__(self, playwright_page, screenshots_base_dir: str = None, refresh_ui_params_per_step: bool = True, enable_element_reordering: bool = True):
        self.page = playwright_page
        self.screenshots_base_dir = screenshots_base_dir or "screenshots"
        self._refresh_ui_params_per_step = refresh_ui_params_per_step
        self._ui_params_cache = None
        self._enable_element_reordering = enable_element_reordering
        self.page_pre_actions: List[Dict[str, Any]] = []  # Store {element, coordinates, op}
    
    async def load_mhtml(self, mhtml_path: str) -> bool:
        """Load MHTML file into Playwright page. Clears page state but preserves page_pre_actions."""
        try:
            if not os.path.exists(mhtml_path):
                print(f"❌ MHTML file not found: {mhtml_path}")
                return False
            
            # Clear page state by navigating to blank page first
            # This closes any open menus/dropdowns from previous MHTML
            # Note: We DON'T clear page_pre_actions here - those are handled by should_reset_page_pre_actions
            await self.page.goto('about:blank', wait_until='domcontentloaded', timeout=5000)
            await asyncio.sleep(0.1)  # Small delay to ensure page is cleared
            
            abs_path = os.path.abspath(mhtml_path)
            file_url = f"file://{abs_path}"
            
            await self.page.goto(file_url, wait_until='domcontentloaded', timeout=10000)
            await self.page.wait_for_load_state('networkidle')
            
            print(f"✅ Loaded MHTML: {os.path.basename(mhtml_path)}")
            return True
            
        except Exception as e:
            print(f"❌ Error loading MHTML {mhtml_path}: {e}")
            return False
    
    def _generate_ui_params(self) -> Dict[str, Any]:
        """Generate random UI modification parameters using diverse design styles with WCAG contrast compliance."""
        return generate_diverse_ui_params()
    
    def set_refresh_ui_params_per_step(self, refresh: bool):
        """Set whether to refresh UI parameters at each step or reuse cached values for trajectory."""
        self._refresh_ui_params_per_step = refresh
        if refresh:
            self._ui_params_cache = None  # Clear cache when enabling per-step refresh
    
    def reset_ui_params_cache(self):
        """Reset the cached UI parameters (useful when starting a new trajectory)."""
        self._ui_params_cache = None
    
    def set_enable_element_reordering(self, enable: bool):
        """Set whether to reorder DOM elements (buttons, links) in the same container.
        
        Args:
            enable: If True, elements will be reordered unless they are intentionally 
                   alphabetically ordered. If False, elements keep their original order.
        """
        self._enable_element_reordering = enable
    
    async def inject_ui_modifications(self) -> Optional[Dict[str, Any]]:
        """Inject random UI modifications: colors, fonts, styles, and reorder DOM elements.
        Returns the parameters used, or None on error."""
        try:
            # Use cached params if refresh_per_step is False, otherwise generate new ones
            if self._refresh_ui_params_per_step or self._ui_params_cache is None:
                params = self._generate_ui_params()
                self._ui_params_cache = params
            else:
                params = self._ui_params_cache
            
            # Make a copy of params for return
            params_return = params.copy()
            
            # Add reordering flag to params
            params_with_reorder = params.copy()
            params_with_reorder['enableElementReordering'] = self._enable_element_reordering
            
            # Generate JavaScript injection code based on design style
            injection_js = generate_injection_js(params)
            
            # Execute the generated JavaScript
            await self.page.evaluate(injection_js, params_with_reorder)
            print("✅ Random UI modifications injected")
            return params_return
            
        except Exception as e:
            print(f"⚠️ Error injecting UI modifications: {e}")
            return None

    def _calculate_center(self, box: Dict[str, float]) -> Tuple[int, int]:
        """Calculate center coordinates from bounding box."""
        x = box.get('x', 0)
        y = box.get('y', 0)
        width = box.get('width', 0)
        height = box.get('height', 0)
        return (int(x + width / 2), int(y + height / 2))

    async def find_element_by_pos_info(
        self, pos_element: Union[str, List[str]], target_element_type: str, target_element_text: str
    ) -> Optional[Dict[str, Any]]:
        """Find element using pos_element information with priority cascade strategy.
        
        Raises:
            ElementLocatorError: If element cannot be found with 100% confidence
            (ElementNotFoundError, AmbiguousMatchError, etc.)
        """
        # Normalize input: if it's a list, use the first element
        if isinstance(pos_element, list):
            if not pos_element:
                raise ElementNotFoundError("Empty pos_element list provided")
            pos_element = pos_element[0]
        
        # ElementLocatorError (including AmbiguousMatchError, ElementNotFoundError) should propagate
        locator = ElementLocator(pos_element, target_element_type, target_element_text)
        element = await locator.find_element(self.page)
        
        bounding_box = await element.bounding_box()
        if not bounding_box:
            raise ElementNotFoundError("Element found but is not visible (no bounding box).")
        
        center_x, center_y = self._calculate_center(bounding_box)

        return {
            'coordinates': (center_x, center_y),
            'bounding_box': (bounding_box['x'], bounding_box['y'], bounding_box['width'], bounding_box['height']),
            'locator': element,
            'original_box': locator.original_box  # Include for debug highlighting
        }
    
    async def _highlight_element(self, element_locator):
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

    async def _highlight_original_box(self, original_box):
        """Debug helper: Visually highlight the original bounding box from pos_candidate."""
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
                        position: 'fixed',
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
                    document.body.appendChild(overlay);
                }
            """, original_box)
        except Exception as e:
            print(f"⚠️ Could not highlight original box: {e}")

    async def get_element_coordinates(self, pos_element: Union[str, List[str]]) -> Optional[Tuple[Tuple[int, int], Dict[str, float]]]:
        """Get element coordinates after UI modifications."""
        element_info = await self.find_element_by_pos_info(pos_element)
        if not element_info:
            return None
        
        element_locator = element_info.get('locator')
        original_box = element_info.get('original_box')

        # Highlight original box from pos_candidate (green dashed border)
        if original_box:
            await self._highlight_original_box(original_box)

        # Highlight found element (red solid outline)
        if element_locator:
            try:
                await element_locator.evaluate("el => el?.setAttribute('data-modified', 'true')")
                await self._highlight_element(element_locator)
            except Exception as e:
                print(f"⚠️ Could not mark element as modified: {e}")

        print(f"Found element at coordinates: {element_info['coordinates']} with bounding box: {element_info['bounding_box']}")
        return element_info['coordinates'], element_info['bounding_box']
    
    async def take_screenshot(self, step_index: int, action: str, bounding_box: Optional[Tuple[float, float, float, float]] = None) -> Tuple[str, Optional[Tuple[float, float]]]:
        """Take screenshot and save it.
        
        If bounding_box is provided (x, y, width, height), takes a full-page screenshot,
        crops it to 1920x1080 to include the entire bounding box, and saves the cropped image.
        Otherwise, takes a full page screenshot.
        
        Returns:
            Tuple of (filepath, crop_offset) where crop_offset is (crop_left, crop_top) 
            if screenshot was cropped, None otherwise. This offset can be used to convert 
            coordinates from full-page frame to cropped frame.
        """
        try:
            filename = f"step_{step_index}_{action.lower()}.png"
            filepath = os.path.join(self.screenshots_base_dir, filename)
            
            if bounding_box:
                # Ensure viewport is at least 1920x1080 (should already be set in main.py, but check to be safe)
                # This ensures the page layout is wide enough for cropping
                try:
                    current_viewport = self.page.viewport_size
                    if not current_viewport or current_viewport.get('width', 0) < 1920 or current_viewport.get('height', 0) < 1080:
                        await self.page.set_viewport_size({"width": 1920, "height": 1080})
                        await asyncio.sleep(0.2)  # Allow layout to adjust
                except Exception:
                    # If viewport_size is not available, just set it
                    await self.page.set_viewport_size({"width": 1920, "height": 1080})
                    await asyncio.sleep(0.2)
                
                # Take full-page screenshot
                temp_filepath = filepath + ".tmp.png"
                await self.page.screenshot(path=temp_filepath, full_page=True)
                
                # Get current scroll position and page dimensions to convert viewport-relative bbox to absolute page coordinates
                page_info = await self.page.evaluate("""
                    () => ({
                        scrollX: window.scrollX,
                        scrollY: window.scrollY,
                        pageWidth: document.documentElement.scrollWidth,
                        pageHeight: document.documentElement.scrollHeight
                    })
                """)
                
                # Convert bounding box from viewport-relative to absolute page coordinates
                # Note: bounding_box is relative to viewport at the time it was measured
                # We need to account for the viewport change if it happened
                x, y, width, height = bounding_box
                bbox_left = x + page_info['scrollX']
                bbox_top = y + page_info['scrollY']
                bbox_right = bbox_left + width
                bbox_bottom = bbox_top + height
                
                # Calculate 1920x1080 crop region that includes the entire bounding box
                crop_width = 1920
                crop_height = 1080
                padding = 20  # Padding around bounding box
                
                # Calculate crop region center to include bounding box with padding
                bbox_center_x = (bbox_left + bbox_right) / 2
                bbox_center_y = (bbox_top + bbox_bottom) / 2
                
                # Start with crop centered on bounding box
                crop_left = bbox_center_x - crop_width / 2
                crop_top = bbox_center_y - crop_height / 2
                
                # Adjust if bounding box with padding would be cut off
                if bbox_left - padding < crop_left:
                    crop_left = max(0, bbox_left - padding)
                if bbox_right + padding > crop_left + crop_width:
                    crop_left = max(0, bbox_right + padding - crop_width)
                
                if bbox_top - padding < crop_top:
                    crop_top = max(0, bbox_top - padding)
                if bbox_bottom + padding > crop_top + crop_height:
                    crop_top = max(0, bbox_bottom + padding - crop_height)
                
                # Load full-page screenshot and crop
                img = Image.open(temp_filepath)
                page_width, page_height = img.size
                
                # Clamp crop coordinates to image boundaries
                crop_left = max(0, min(crop_left, page_width - crop_width))
                crop_top = max(0, min(crop_top, page_height - crop_height))
                
                # Ensure we don't crop more than the image size
                actual_crop_width = min(crop_width, page_width - int(crop_left))
                actual_crop_height = min(crop_height, page_height - int(crop_top))
                
                # Crop the image
                crop_left_int = int(crop_left)
                crop_top_int = int(crop_top)
                cropped_img = img.crop((
                    crop_left_int,
                    crop_top_int,
                    crop_left_int + actual_crop_width,
                    crop_top_int + actual_crop_height
                ))
                
                # If cropped image is smaller than 1920x1080 (e.g., page was smaller), pad it
                paste_x = 0
                paste_y = 0
                if actual_crop_width < crop_width or actual_crop_height < crop_height:
                    # Create a new image with the target size and paste the cropped image
                    # Use white background for padding
                    final_img = Image.new('RGB', (crop_width, crop_height), color='white')
                    # Center the cropped image if it's smaller than target
                    paste_x = (crop_width - actual_crop_width) // 2 if actual_crop_width < crop_width else 0
                    paste_y = (crop_height - actual_crop_height) // 2 if actual_crop_height < crop_height else 0
                    final_img.paste(cropped_img, (paste_x, paste_y))
                    cropped_img = final_img
                
                # Calculate crop_offset: when we pad, the effective crop_left/top shifts
                # because the content is now at (paste_x, paste_y) in the final image
                # So crop_offset should be (crop_left - paste_x, crop_top - paste_y)
                effective_crop_left = crop_left - paste_x
                effective_crop_top = crop_top - paste_y
                
                # Save cropped image
                cropped_img.save(filepath)
                
                # Clean up temp file
                if os.path.exists(temp_filepath):
                    os.remove(temp_filepath)
                
                print(f"📸 Screenshot saved: {filename} (1920x1080, cropped to include element)")
                return filepath, (effective_crop_left, effective_crop_top)
            else:
                # Fallback to full page screenshot
                await self.page.screenshot(path=filepath, full_page=True)
                print(f"📸 Screenshot saved: {filename} (full page)")
                return filepath, None
        except Exception as e:
            print(f"❌ Error taking screenshot: {e}")
            traceback.print_exc()
            return "", None
    
    async def process_action(
        self,
        action_uid: str,
        action_op: str,
        type_action_value: str,
        pos_candidate: str,
        target_element_type: str,
        target_element_text: str,
        step_index: int = None,
        should_reset_page_pre_actions: bool = False
    ) -> Dict[str, Any]:
        """Process a single action entry"""
        print(f"\n🎬 Processing action: {action_uid} ({action_op})")

        if should_reset_page_pre_actions:
            self.page_pre_actions = []

        # Replay previous interactions to open menus/hover states
        if self.page_pre_actions:
            for prev_state in self.page_pre_actions:
                prev_element = prev_state.get('element')
                prev_coords = prev_state.get('coordinates')
                prev_op = prev_state.get('op', 'CLICK')
                prev_value = prev_state.get('value')  # Stored value for SELECT/TYPE actions
                
                if not prev_element or not prev_coords:
                    continue
                
                prev_op_upper = prev_op.upper()
                
                if prev_op_upper == 'CLICK':
                    # For label elements, find and click the associated input checkbox/radio
                    tag_name = await prev_element.evaluate("el => el.tagName.toLowerCase()")
                    if tag_name == 'label':
                        # Try to find associated input checkbox/radio
                        label_for = await prev_element.get_attribute('for')
                        input_element = None
                        
                        if label_for:
                            # Find input by id
                            input_element = self.page.locator(f"#{label_for}")
                            if await input_element.count() == 0:
                                input_element = None
                        else:
                            # Label without 'for' - find input inside label
                            input_element = prev_element.locator("input[type='checkbox'], input[type='radio']")
                            if await input_element.count() == 0:
                                input_element = None
                        
                        if input_element:
                            # For checkbox/radio, use check() which is more reliable than click()
                            try:
                                input_type = await input_element.evaluate("el => el.type")
                                is_checked = await input_element.is_checked()
                                
                                # Use check()/uncheck() for checkbox/radio - more reliable
                                if input_type == 'checkbox':
                                    if not is_checked:
                                        await input_element.check(timeout=5000)
                                        print(f"✅ Replayed CLICK interaction (checkbox checked)")
                                    else:
                                        await input_element.uncheck(timeout=5000)
                                        print(f"✅ Replayed CLICK interaction (checkbox unchecked)")
                                elif input_type == 'radio':
                                    await input_element.check(timeout=5000)
                                    print(f"✅ Replayed CLICK interaction (radio checked)")
                                else:
                                    # Fallback to click for other input types
                                    await input_element.hover(timeout=2000)
                                    await asyncio.sleep(0.2)
                                    await input_element.click(timeout=5000)
                                    await asyncio.sleep(0.2)
                                    print(f"✅ Replayed CLICK interaction (input)")
                                
                                # Trigger change event to ensure JavaScript handlers fire
                                await input_element.evaluate("el => el.dispatchEvent(new Event('change', { bubbles: true }))")
                                await asyncio.sleep(0.3)
                            except Exception as e:
                                print(f"⚠️ Error with check()/uncheck(), falling back to click: {e}")
                                try:
                                    await input_element.hover(timeout=2000)
                                    await asyncio.sleep(0.2)
                                    await input_element.click(timeout=5000)
                                    await asyncio.sleep(0.3)
                                    print(f"✅ Replayed CLICK interaction (fallback click)")
                                except Exception as e2:
                                    print(f"⚠️ Fallback click also failed: {e2}")
                                    # Final fallback to coordinates
                                    await self.page.mouse.move(prev_coords[0], prev_coords[1])
                                    await asyncio.sleep(0.2)
                                    await self.page.mouse.click(prev_coords[0], prev_coords[1])
                                    await asyncio.sleep(0.3)
                                    print(f"✅ Replayed CLICK interaction (using coordinates)")
                        else:
                            # No input found, use stored coordinates (should be checkbox location)
                            await self.page.mouse.move(prev_coords[0], prev_coords[1])
                            await asyncio.sleep(0.2)
                            await self.page.mouse.click(prev_coords[0], prev_coords[1])
                            await asyncio.sleep(0.3)
                            print(f"✅ Replayed CLICK interaction (using coordinates)")
                    else:
                        # For non-label elements, use element click
                        await prev_element.hover(timeout=2000)
                        await asyncio.sleep(0.2)
                        await prev_element.click(timeout=2000)
                        await asyncio.sleep(0.2)
                        print(f"✅ Replayed CLICK interaction")
                
                elif prev_op_upper == 'SELECT':
                    await prev_element.hover(timeout=2000)
                    await asyncio.sleep(0.2)
                    # Use stored value to select the correct option
                    if prev_value:
                        try:
                            await prev_element.select_option(prev_value, timeout=2000)
                            print(f"✅ Replayed SELECT interaction with value: {prev_value}")
                        except Exception:
                            # Fallback: try selecting by visible text
                            try:
                                await prev_element.select_option(label=prev_value, timeout=2000)
                                print(f"✅ Replayed SELECT interaction with label: {prev_value}")
                            except Exception as e:
                                print(f"⚠️ Could not select value '{prev_value}', hover only: {e}")
                    else:
                        print(f"⚠️ SELECT action has no stored value, hover only")
                    await asyncio.sleep(0.2)
                
                elif prev_op_upper == 'SCROLL':
                    await prev_element.scroll_into_view_if_needed(timeout=2000)
                    await asyncio.sleep(0.2)
                    print(f"✅ Replayed SCROLL interaction")
                
                elif prev_op_upper.startswith('TYPE'):
                    # Use stored value if available, otherwise use current type_action_value
                    value_to_type = prev_value if prev_value else type_action_value
                    await prev_element.fill(value_to_type, timeout=2000)
                    await asyncio.sleep(0.2)
                    print(f"✅ Replayed TYPE interaction with value: {value_to_type}")
                elif prev_op_upper == 'HOVER':
                    await prev_element.hover(timeout=2000)
                    await asyncio.sleep(0.2)
                    print(f"✅ Replayed HOVER interaction")
                else:
                    raise ValueError(f"Unknown action type: {prev_op_upper}")

        ui_params = {}
        ui_params = await self.inject_ui_modifications()
        print(f"Finding element by pos_candidate: {pos_candidate}")
        
        # Get full element info (including locator)
        # This will raise ElementLocatorError if element cannot be found with 100% confidence
        element_info = await self.find_element_by_pos_info(pos_candidate, target_element_type, target_element_text)
        
        element = element_info.get('locator')
        original_box = element_info.get('original_box')
        augmentation_success = True
        
        # For label elements with checkbox/radio, find the actual input for better coordinates
        if element:
            tag_name = await element.evaluate("el => el.tagName.toLowerCase()")
            if tag_name == 'label' and action_op.upper() == 'CLICK':
                # Try to find associated input checkbox/radio
                label_for = await element.get_attribute('for')
                input_element = None
                
                if label_for:
                    input_element = self.page.locator(f"#{label_for}")
                    if await input_element.count() == 0:
                        input_element = None
                else:
                    input_element = element.locator("input[type='checkbox'], input[type='radio']")
                    if await input_element.count() == 0:
                        input_element = None
                
                if input_element:
                    # Use input element instead of label for better coordinates
                    element = input_element
                    print(f"  📌 Using input checkbox/radio instead of label")
        
        # Get coordinates and bounding box from the (possibly corrected) element
        bbox = await element.bounding_box()
        if bbox:
            coordinates = (int(bbox['x'] + bbox['width'] / 2), int(bbox['y'] + bbox['height'] / 2))
            bounding_box = (bbox['x'], bbox['y'], bbox['width'], bbox['height'])
        else:
            # Fallback to original coordinates
            coordinates = element_info.get('coordinates')
            bounding_box = element_info.get('bounding_box')
        
        # # Do highlighting (extracted from get_element_coordinates)
        # if original_box:
        #     await self._highlight_original_box(original_box)
        # if element:
        #     try:
        #         await element.evaluate("el => el?.setAttribute('data-modified', 'true')")
        #         await self._highlight_element(element)
        #     except Exception as e:
        #         print(f"⚠️ Could not mark element as modified: {e}")
        
        print(f"Found element at coordinates: {coordinates} with bounding box: {bounding_box}")
        
        # Store element info for next step (including value for SELECT/TYPE actions)
        if element and coordinates:
            stored_value = None
            if action_op.upper() == 'SELECT' or action_op.upper().startswith('TYPE'):
                stored_value = type_action_value if type_action_value else None
            
            self.page_pre_actions.append({
                'element': element,
                'coordinates': coordinates,
                'op': action_op,
                'value': stored_value,  # Store value for SELECT/TYPE actions
            })
        
        # Only take screenshot if element was found with 100% confidence
        await asyncio.sleep(0.2)
        screenshot_path, crop_offset = await self.take_screenshot(step_index, action_op, bounding_box)
        
        # Convert coordinates from full-page frame to cropped 1920x1080 frame if screenshot was cropped
        converted_coordinates = coordinates
        converted_bounding_box = bounding_box
        if crop_offset is not None and bounding_box is not None:
            crop_left, crop_top = crop_offset
            
            # Get scroll position to convert viewport-relative coordinates to absolute page coordinates
            scroll_info = await self.page.evaluate("() => ({ scrollX: window.scrollX, scrollY: window.scrollY })")
            
            # Convert bounding box from viewport-relative to absolute, then to cropped frame
            x, y, width, height = bounding_box
            bbox_page_x = x + scroll_info['scrollX']
            bbox_page_y = y + scroll_info['scrollY']
            
            # Convert to cropped frame coordinates
            converted_bounding_box = (
                bbox_page_x - crop_left,
                bbox_page_y - crop_top,
                width,
                height
            )
            
            # Convert center coordinates (coordinates are viewport-relative center of bounding box)
            if coordinates:
                # Convert from viewport-relative to page coordinates, then to cropped frame
                coord_page_x = coordinates[0] + scroll_info['scrollX']
                coord_page_y = coordinates[1] + scroll_info['scrollY']
                converted_coordinates = (
                    int(coord_page_x - crop_left),
                    int(coord_page_y - crop_top)
                )

        return {
            'action_uid': action_uid,
            'op': action_op,
            'augmentation_success': augmentation_success,
            'coordinates': converted_coordinates,
            'bounding_box': converted_bounding_box,
            'screenshot': screenshot_path,
            'ui_params': ui_params  # Include UI modification parameters used for this step
        }